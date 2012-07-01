# ============================================================
#
# Copyright (C) 2011, 2012 Jan Moringen <jmoringe@techfak.uni-bielefeld.de>
#
# This file may be licensed under the terms of the
# GNU Lesser General Public License Version 3 (the ``LGPL''),
# or (at your option) any later version.
#
# Software distributed under the License is distributed
# on an ``AS IS'' basis, WITHOUT WARRANTY OF ANY KIND, either
# express or implied. See the LGPL for the specific language
# governing rights and limitations.
#
# You should have received a copy of the LGPL along with this
# program. If not, go to http://www.gnu.org/licenses/lgpl.html
# or write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# The development of this software was supported by:
#   CoR-Lab, Research Institute for Cognition and Robotics
#     Bielefeld University
#
# ============================================================

"""
Package containing pattern implementations like RPC based on the basic
participants L{rsb.Listener} and L{rsb.Informer}.

@author: jmoringe
@author: jwienke
"""

import uuid
import threading

import rsb
from future import Future, DataFuture

# TODO superclass for RSB Errors?
class RemoteCallError (RuntimeError):
    """
    Errors of this class are raised when a call to a remote method
    fails for some reason.

    @author: jmoringe
    """
    def __init__(self, scope, method, message = None):
        super(RemoteCallError, self).__init__(message)
        self._scope  = scope
        self._method = method

    def getScope(self):
        return self._scope

    scope = property(getScope)

    def getMethod(self):
        return self._method

    method = property(getMethod)

    def __str__(self):
        s = 'failed to call method "%s" on remote server with scope %s' \
            % (self.method.name, self.scope)
        # TODO(jmoringe): .message seems to be deprecated
        if self.message:
            s += ': %s' % self.message
        return s

######################################################################
#
# Method and Server base classes
#
######################################################################

class Method (object):
    """
    Objects of this class are methods which are associated to a local
    or remote server. Within a server, each method has a unique name.

    This class is primarily intended as a superclass for local and
    remote method classes.

    @author: jmoringe
    """
    def __init__(self, server, name, requestType, replyType):
        """
        Create a new Method object for the method named B{name}
        provided by B{server}.

        @param server: The remote or local server to which the method
                       is associated.
        @param name: The name of the method. Unique within a server.
        @param requestType: The type of the request argument accepted
                            by the method.
        @type  requestType: type
        @param replyType: The type of the replies produced by the
                          method.
        @type  replyType: type
        """
        self._server      = server
        self._name        = name
        self._listener    = None
        self._informer    = None
        self._requestType = requestType
        self._replyType   = replyType

    def getServer(self):
        return self._server

    server = property(getServer)

    def getName(self):
        return self._name

    name = property(getName)

    def getListener(self):
        if self._listener is None:
            self._listener = self.makeListener()
        return self._listener

    listener = property(getListener)

    def getInformer(self):
        if self._informer is None:
            self._informer = self.makeInformer()
        return self._informer

    informer = property(getInformer)

    def getRequestType(self):
        return self._requestType

    requestType = property(getRequestType)

    def getReplyType(self):
        return self._replyType

    replyType = property(getReplyType)

    def deactivate(self):
        if not self._informer is None:
            self._informer.deactivate()
            self._informer = None
        if not self._listener is None:
            self._listener.deactivate()
            self._listener = None

    def __str__(self):
        return '<%s "%s" at 0x%x>' % (type(self).__name__, self.name, id(self))

    def __repr__(self):
        return str(self)

class Server (rsb.Participant):
    """
    Objects of this class represent local or remote serves. A server
    is basically a collection of named methods that are bound to a
    specific scope.

    This class is primarily intended as a superclass for local and
    remote server classes.

    @author: jmoringe
    """

    def __init__(self, scope, config = None):
        """
        Create a new Server object that provides its methods under the
        scope B{scope}.

        @param scope: The under which methods of the server are
                      provided.
        @param config: The transport configuration that should be used
                       for communication performed by this server.
        @type config: ParticipantConfig
        """
        super(Server, self).__init__(scope)

        self.__active = False
        if config is None:
            self.__config = rsb.getDefaultParticipantConfig()
        else:
            self.__config = config
        self._methods = {}

        self.activate()

    def __del__(self):
        if self.__active:
            self.deactivate()

    def getConfig(self):
        return self.__config

    config = property(getConfig)

    def getMethods(self):
        return self._methods.values()

    methods = property(getMethods)

    def getMethod(self, name):
        if name in self._methods:
            return self._methods[name]

    def addMethod(self, method):
        self._methods[method.name] = method

    def removeMethod(self, method):
        del self._methods[method.name]

    # State management

    def activate(self):
        self.__active = True

    def deactivate(self):
        if not self.__active:
            raise RuntimeError, 'Trying to deactivate inactive server'

        self.__active = False

        for m in self._methods.values():
            m.deactivate()

    # Printing

    def __str__(self):
        return '<%s with %d method(s) at 0x%x>' % (type(self).__name__, len(self._methods), id(self))

    def __repr__(self):
        return str(self)

######################################################################
#
# Local Server
#
######################################################################

class LocalMethod (Method):
    """
    Objects of this class implement and make available methods of a
    local server.

    The actual behavior of methods is implemented by invoking
    arbitrary user-supplied callables.

    @author: jmoringe
    """
    def __init__(self, server, name, func, requestType, replyType):
        super(LocalMethod, self).__init__(server, name, requestType, replyType)
        self._func = func
        self.listener # force listener creation

    def makeListener(self):
        listener = rsb.Listener(self.server.scope
                                .concat(rsb.Scope("/request"))
                                .concat(rsb.Scope('/' + self.name)),
                                self.server.config)
        listener.addHandler(self._handleRequest)
        return listener

    def makeInformer(self):
        return rsb.Informer(self.server.scope
                            .concat(rsb.Scope("/reply"))
                            .concat(rsb.Scope('/' + self.name)),
                            object,
                            config = self.server.config)

    def _handleRequest(self, request):
        if request.method is None or request.method != 'REQUEST':
            return
        userInfos = {}
        causes    = [ request.id ]
        isError   = False
        try:
            if self.requestType is type(None):
                assert(request.data is None)
                result = self._func()
            else:
                result = self._func(request.data)
            resultType = self.replyType
        except Exception, e:
            isError                 = True
            userInfos['rsb:error?'] = '1'
            result                  = str(e)
            resultType              = str

        if isinstance(result, rsb.Event):
            reply = result
            reply.causes += causes
        else:
            # this check is required because the reply informer is
            # created with type 'object' to enable throwing exceptions
            if not isError and not isinstance(result, self.replyType):
                raise ValueError("The result '%s' (of type %s) of method %s does not match the method's declared return type %s."
                                 % (result, type(result), self.name, self.replyType))
            reply = rsb.Event(scope     = self.informer.scope,
                              method    = 'REPLY',
                              data      = result,
                              type      = resultType,
                              userInfos = userInfos,
                              causes    = causes)
        self.informer.publishEvent(reply)

class LocalServer (Server):
    """
    Objects of this class associate a collection of method objects
    which are implemented by callback functions with a scope under
    which these methods are exposed for remote clients.

    @author: jmoringe
    """
    def __init__(self, scope, config = None):
        """
        Creates a new L{LocalServer} object that exposes methods under
        a the scope B{scope}.

        @param scope: The scope under which the methods of the newly
                      created server should be provided.
        @type scope: Scope
        @param config: The transport configuration that should be used
        for communication performed by this server.
        @type config: ParticipantConfig

        See also: L{createServer}
        """
        super(LocalServer, self).__init__(scope, config)

    def addMethod(self, name, func, requestType = object, replyType = object):
        """
        Add a method named B{name} that is implemented by B{func}.

        @param name: The name of of the new method.
        @type name: str
        @param func: A callable object or a single argument that
                     implements the desired behavior of the new
                     method.
        @param requestType: A type object indicating the type of
                            request data passed to the method.
        @type requestType: type
        @param replyType: A type object indicating the type of reply
                          data of the method.
        @type replyType: type
        @return: The newly created method.
        @rtype: LocalMethod
        """
        method = LocalMethod(self, name, func, requestType, replyType)
        super(LocalServer, self).addMethod(method)
        return method

    def removeMethod(self, method):
        if isinstance(method, str):
            method = self.getMethod(method)
        super(LocalServer, self).removeMethod(method)

######################################################################
#
# Remote Server
#
######################################################################

class RemoteMethod (Method):
    """
    Objects of this class represent methods provided by a remote
    server. Method objects are callable like regular bound method
    objects.

    @author: jmoringe
    """
    def __init__(self, server, name, requestType, replyType):
        super(RemoteMethod, self).__init__(server, name, requestType, replyType)
        self._calls = {}
        self._lock  = threading.RLock()

    def makeListener(self):
        listener = rsb.Listener(self.server.scope
                                .concat(rsb.Scope("/reply"))
                                .concat(rsb.Scope('/' + self.name)),
                                self.server.config)
        listener.addHandler(self._handleReply)
        return listener

    def makeInformer(self):
        return rsb.Informer(self.server.scope
                            .concat(rsb.Scope("/request"))
                            .concat(rsb.Scope('/' + self.name)),
                            self.requestType,
                            config = self.server.config)

    def _handleReply(self, event):
        if event.method is None            \
                or event.method != 'REPLY' \
                or not event.causes:
            return
        key = event.causes[0]
        with self._lock:
            # We can receive reply events which aren't actually
            # intended for us. We ignore these.
            if not key in self._calls:
                return

            result = self._calls[key] # The result future
            del self._calls[key]
        if 'rsb:error?' in event.metaData.userInfos:
            result.setError(event.data)
        else:
            result.set(event)

    def __call__(self, arg = None):
        """
        Call the method synchronously with argument B{arg}, returning
        the value returned by the remote method.

        If B{arg} is an instance of L{Event}, an L{Event} containing
        the object returned by the remote method as payload is
        returned. If B{arg} is of any other type, return the object
        that was returned by the remote method.

        The call to this method blocks until a result is available or
        an error occurs.

        Examples:
        >>> myServer.echo('bla')
        'bla'
        >>> myServer.echo(Event(scope = myServer.scope, data = 'bla', type = str))
        Event[id = ..., data = 'bla', ...]

        @param arg: The argument object that should be passed to the
                    remote method. A converter has to be available for
                    the type of B{arg}.
        @return: The object that was returned by the remote method.
        @raise RemoteCallError: If invoking the remote method fails or
                                the remote method itself produces an
                                error.
        @see: L{async}
        """
        return self.async(arg).get()

    def async(self, arg = None):
        """
        Call the method asynchronously with argument B{arg}, returning
        a L{Future} instance that can be used to retrieve the result.

        If B{arg} is an instance of L{Event}, the result of the method
        call is an L{Event} containing the object returned by the
        remote method as payload. If B{arg} is of any other type, the
        result is the payload of the method call is the object that
        was returned by the remote method.

        The call to this method returns immediately, even if the
        remote method did produce a result yet. The returned L{Future}
        instance has to be used to retrieve the result.

        Examples:
        >>> myServer.echo.async('bla')
        <Future running at 3054cd0>
        >>> myServer.echo.async('bla').get()
        'bla'
        >>> myServer.echo.async(Event(scope = myServer.scope, data = 'bla', type = str)).get()
        Event[id = ..., data = 'bla', ...]

        @param arg: The argument object that should be passed to the
                    remote method. A converter has to be available for
                    the type of B{arg}.
        @return: A L{Future} or L{DataFuture} instance that can be
                 used to check the success of the method call, wait
                 for the result and retrieve the result.
        @rtype: L{Future} or L{DataFuture}
        @raise RemoteCallError: If an error occurs before the remote
                                was invoked.
        @see: L{__call__}
        """
        self.listener # Force listener creation

        if isinstance(arg, rsb.Event):
            event        = arg
            event.scope  = self.informer.scope
            event.method = 'REQUEST'
            result       = Future()
        else:
            event = rsb.Event(scope  = self.informer.scope,
                              method = 'REQUEST',
                              data   = arg,
                              type   = type(arg))
            result = DataFuture()

        try:
            with self._lock:
                event = self.informer.publishEvent(event)
                self._calls[event.id] = result
        except Exception, e:
            raise RemoteCallError(self.server.scope, self, message = repr(e))
        return result

    def __str__(self):
        return '<%s "%s" with %d in-progress calls at 0x%x>' \
            % (type(self).__name__, self.name, len(self._calls), id(self))

    def __repr__(self):
        return str(self)

class RemoteServer (Server):
    """
    Objects of this class represent remote servers in a way that
    allows calling methods on them as if they were local.

    @author: jmoringe
    """
    def __init__(self, scope, config = None):
        """
        Create a new L{RemoteServer} object that provides its methods
        under the scope B{scope}.

        @param scope: The common super-scope under which the methods
        of the remote created server are provided.
        @type scope: Scope
        @param config: The transport configuration that should be used
        for communication performed by this server.
        @type config: ParticipantConfig
        @see: L{createRemoteServer}
        """
        super(RemoteServer, self).__init__(scope, config)

    def __getattr__(self, name):
        try:
            super(RemoteServer, self).__getattr__(name)
        except AttributeError:
            method = self.getMethod(name)
            if method is None:
                method = RemoteMethod(self, name, object, object)
                self.addMethod(method)
            return method
