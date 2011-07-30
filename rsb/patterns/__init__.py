# ============================================================
#
# Copyright (C) 2011 Jan Moringen <jmoringe@techfak.uni-bielefeld.de>
#
# This program is free software; you can redistribute it
# and/or modify it under the terms of the GNU General
# Public License as published by the Free Software Foundation;
# either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# ============================================================

import uuid
import threading

import rsb

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
        if self.message:
            s += ': %s' % self.message
        return s

class TimeoutError (RemoteCallError):
    """
    Errors of this class are raised when a call to a remote method
    does not complete within a given amount of time.

    @author: jmoringe
    """
    def __init__(self, scope, method):
        super(TimeoutError, self).__init__(scope, method)

class RemoteExecutionError (RemoteCallError):
    """
    Error of this class are raised when a call to a remote method
    succeeds in calling the method on the remote side but fails in the
    actual remote method.

    @author: jmoringe
    """
    def __init__(self, scope, method, message):
        super(RemoteExecutionError, self).__init__(scope, method, message = message)

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
            self._inforer = None
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

    def __init__(self, scope):
        super(Server, self).__init__(scope)
        self._methods = {}

    def __del__(self):
        self.deactivate

    def getMethod(self, name):
        if name in self._methods:
            return self._methods[name]

    def addMethod(self, method):
        self._methods[method.name] = method

    def removeMethod(self, method):
        del self._methods[method.name]

    def deactivate(self):
        map(lambda x: x.deactivate, self._methods.values())

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
    def __init__(self, server, name, func, requestType, replyType):
        super(LocalMethod, self).__init__(server, name, requestType, replyType)
        self._func = func

    def makeListener(self):
        listener = rsb.Listener(self.server.scope
                                .concat(rsb.Scope("/request"))
                                .concat(rsb.Scope('/' + self.name)))
        listener.addHandler(self._handleRequest)

    def makeInformer(self):
        return rsb.Informer(self.server.scope
                            .concat(rsb.Scope("/reply"))
                            .concat(rsb.Scope('/' + self.name)),
                            self.replyType)

    def _handleRequest(self, arg):
        self.informer.publishData(self._func(arg))

class LocalServer (Server):
    """
    @author: jmoringe
    """
    def __init__(self, scope):
        """

        @param scope: The scope under which the methods of the newly
        created server should be provided.
        """
        super(LocalServer, self).__init__(scope)

    def addMethod(self, name, func, requestType, replyType):
        """
        Add a method named name that is implemented by function.
        @param name: The name of of the new method.
        @param func: A callable object or a single argument that
                     implements the desired behavior of the new
                     method.
        @param requestType: A type object indicating the type of
                            request data passed to the method.
        @param replyType: A type object indicating the type of reply
                          data of the method.
        @return: The newly created method
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

class Call (object):
    """
    @author: jmoringe
    """
    def __init__(self, id, lock):
        self._id        = id
        self._result    = None
        self._lock      = lock
        self._condition = threading.Condition(lock = self._lock)

    def getId(self):
        return self._id

    id = property(getId)

    def getResult(self):
        return self._result

    def setResult(self, newValue):
        with self._lock:
            self._result = newValue
            self._condition.notify()

    result = property(getResult, setResult)

    def wait(self, timeout):
        with self._lock:
            while self._result is None:
                self._condition.wait(timeout = timeout)
                break # TODO protect against early wakeup

class RemoteMethod (Method):
    """
    @author: jmoringe
    """
    def __init__(self, server, name, requestType, replyType):
        super(RemoteMethod, self).__init__(server, name, requestType, replyType)
        self._calls = {}
        self._lock  = threading.RLock()

    def makeListener(self):
        listener = rsb.Listener(self.server.scope
                                .concat(rsb.Scope("/reply"))
                                .concat(rsb.Scope('/' + self.name)))
        listener.addHandler(self._handleReply)
        return listener

    def makeInformer(self):
        return rsb.Informer(self.server.scope
                            .concat(rsb.Scope("/request"))
                            .concat(rsb.Scope('/' + self.name)),
                            self.requestType)

    def _handleReply(self, event):
        key  = uuid.UUID(event.metaData.userInfos['ServerRequestId'])
        with self._lock:
            # We can receive reply events which aren't actually
            # intended for us. We ignore these
            if key in self._calls:
                self._calls[key].result = event

    def __call__(self, arg):
        self.listener # Force listener creation

        call = Call(uuid.uuid1(), self._lock)
        event = rsb.Event(scope     = self.informer.scope,
                          data      = arg,
                          type      = str,
                          userInfos = { 'ServerRequestId': str(call.id) })
        with self._lock:
            self._calls[call.id] = call
        try:
            self.informer.publishEvent(event)
        except Exception, e:
            raise RemoteCallError(self.server.scope, self, message = str(e))

        try:
            call.wait(timeout = self.server.timeout)

            if call.result is None:
                raise TimeoutError(self.server.scope, self)
            elif 'isException' in call.result.metaData.userInfos:
                raise RemoteExecutionError(self.server.scope, self, call.result.data)
            else:
                return call.result.data
        finally:
            with self._lock:
                del self._calls[call.id]

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
    def __init__(self, scope, timeout = 25):
        """
        Create a new RemoteServer object that provides its methods
        under the scope @a scope.

        @param scope: The common super-scope under which the methods
        of the remote created server are provided.
        @param timeout: The amount of seconds methods calls should
        wait for their replies to arrive before failing.
        """
        super(RemoteServer, self).__init__(scope)
        self._timeout = timeout

    def getTimeout(self):
        return self._timeout

    timeout = property(getTimeout)

    def __getattr__(self, name):
        try:
            super(RemoteServer, self).__getattr__(name)
        except AttributeError:
            method = self.getMethod(name)
            if method is None:
                method = RemoteMethod(self, name)
                self.addMethod(method)
            return method
