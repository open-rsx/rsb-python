# ============================================================
#
# Copyright (C) 2011-2017 Jan Moringen
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
# ============================================================

"""
Contains communication pattern implementations.

For instance, RPC based on the basic participants :obj:`rsb.Listener` and
:obj:`rsb.Informer`.

.. codeauthor:: jmoringe
.. codeauthor:: jwienke
"""

import threading

import rsb
from rsb.eventprocessing import FullyParallelEventReceivingStrategy
import rsb.filter
from rsb.patterns.future import DataFuture, Future


# TODO superclass for RSB Errors?
class RemoteCallError(RuntimeError):
    """
    Represents an error when calling a remote method implementation.

    .. codeauthor:: jmoringe
    """

    def __init__(self, scope, method, error):
        super(RemoteCallError, self).__init__(
            'failed to call method "%s" on remote server with scope %s. '
            'reason: %s'
            % (method.name, scope, error))
        self._scope = scope
        self._method = method

    def get_scope(self):
        return self._scope

    scope = property(get_scope)

    def get_method(self):
        return self._method

    method = property(get_method)

######################################################################
#
# Method and Server base classes
#
######################################################################


class Method(rsb.Participant):
    """
    Base class for methods of local or remote servers.

    Objects of this class are methods which are associated to a local
    or remote server. Within a server, each method has a unique name.

    This class is primarily intended as a superclass for local and
    remote method classes.

    .. codeauthor:: jmoringe
    """

    # TODO scope and name are redundant
    def __init__(self, scope, config,
                 server, name, request_type, reply_type):
        """
        Create a new :obj:`Method` object for the given name and server.

        Args:
            server:
                The remote or local server to which the method is associated.
            name (str):
                The name of the method. Unique within a server.
            request_type (types.TypeType):
                The type of the request argument accepted by the method.
            reply_type (types.TypeType):
                The type of the replies produced by the method.
        """
        super(Method, self).__init__(scope, config)

        self._server = server
        self._name = name
        self._listener = None
        self._informer = None
        self._request_type = request_type
        self._reply_type = reply_type

    def get_server(self):
        return self._server

    server = property(get_server)

    def get_name(self):
        return self._name

    name = property(get_name)

    def get_listener(self):
        if self._listener is None:
            self._listener = self.make_listener()
        return self._listener

    listener = property(get_listener)

    def get_informer(self):
        if self._informer is None:
            self._informer = self.make_informer()
        return self._informer

    informer = property(get_informer)

    def get_request_type(self):
        return self._request_type

    request_type = property(get_request_type)

    def get_reply_type(self):
        return self._reply_type

    reply_type = property(get_reply_type)

    def deactivate(self):
        if self._informer is not None:
            self._informer.deactivate()
            self._informer = None
        if self._listener is not None:
            self._listener.deactivate()
            self._listener = None

        super(Method, self).deactivate()

    def __str__(self):
        return '<%s "%s" at 0x%x>' % (type(self).__name__, self.name, id(self))

    def __repr__(self):
        return str(self)


class Server(rsb.Participant):
    """
    Base class for local or remote servers.

    Objects of this class represent local or remote serves. A server
    is basically a collection of named methods that are bound to a
    specific scope.

    This class is primarily intended as a superclass for local and
    remote server classes.

    .. codeauthor:: jmoringe
    """

    def __init__(self, scope, config):
        """
        Create a :obj:`Server` that provides methods under the given scope.

        Args:
            scope (rsb.Scope):
                The scope under which methods of the server are provided.
            config (rsb.ParticipantConfig):
                The transport configuration that should be used for
                communication performed by this server.
        """
        super(Server, self).__init__(scope, config)

        self.__active = False
        self._methods = {}

        self.activate()

    def __del__(self):
        if self.__active:
            self.deactivate()

    def get_methods(self):
        return list(self._methods.values())

    methods = property(get_methods)

    def get_method(self, name):
        if name in self._methods:
            return self._methods[name]

    def add_method(self, method):
        self._methods[method.name] = method

    def remove_method(self, method):
        del self._methods[method.name]

    # State management

    def activate(self):
        self.__active = True

        super(Server, self).activate()

    def deactivate(self):
        if not self.__active:
            raise RuntimeError('Trying to deactivate inactive server')

        self.__active = False

        for m in list(self._methods.values()):
            m.deactivate()

        super(Server, self).deactivate()

    # Printing

    def __str__(self):
        return '<%s with %d method(s) at 0x%x>' % (type(self).__name__,
                                                   len(self._methods),
                                                   id(self))

    def __repr__(self):
        return str(self)

######################################################################
#
# Local Server
#
######################################################################


class LocalMethod(Method):
    """
    Implements and makes available a method of a local server.

    The actual behavior of methods is implemented by invoking
    arbitrary user-supplied callables.

    .. codeauthor:: jmoringe
    """

    def __init__(self, scope, config,
                 server, name, func, request_type, reply_type,
                 allow_parallel_execution):
        super(LocalMethod, self).__init__(
            scope, config, server, name, request_type, reply_type)

        self._allow_parallel_execution = allow_parallel_execution
        self._func = func
        self.listener  # force listener creation

    def make_listener(self):
        receiving_strategy = None
        if self._allow_parallel_execution:
            receiving_strategy = FullyParallelEventReceivingStrategy()
        listener = rsb.create_listener(self.scope, self.config,
                                       parent=self,
                                       receiving_strategy=receiving_strategy)
        listener.add_filter(rsb.filter.MethodFilter(method='REQUEST'))
        listener.add_handler(self._handle_request)
        return listener

    def make_informer(self):
        return rsb.create_informer(self.scope, self.config,
                                   parent=self,
                                   data_type=object)

    def _handle_request(self, request):
        # Call the callable implementing the behavior of this
        # method. If it does not take an argument
        # (i.e. self.request_type is type(None)), call it without
        # argument. Otherwise pass the payload of the request event to
        # it.
        user_infos = {}
        causes = [request.event_id]
        is_error = False
        try:
            if self.request_type is type(None):
                assert(request.data is None)
                result = self._func()
            elif self.request_type is rsb.Event:
                result = self._func(request)
            else:
                result = self._func(request.data)
            result_type = type(result)
        except Exception as e:
            is_error = True
            user_infos['rsb:error?'] = '1'
            result = str(e)
            result_type = str

        # If the returned result is an event, use it as reply event
        # (after adding the request as cause). Otherwise add all
        # necessary meta-data.
        if isinstance(result, rsb.Event):
            reply = result
            reply.method = 'REPLY'
            reply.causes += causes
        else:
            # This check is required because the reply informer is
            # created with type 'object' to enable throwing exceptions
            if not is_error and not isinstance(result, self.reply_type):
                raise ValueError("The result '%s' (of type %s) "
                                 "of method %s does not match "
                                 "the method's declared return type %s."
                                 % (result, result_type,
                                    self.name, self.reply_type))
            reply = rsb.Event(scope=self.informer.scope,
                              method='REPLY',
                              data=result,
                              data_type=result_type,
                              user_infos=user_infos,
                              causes=causes)

        # Publish the reply event.
        self.informer.publish_event(reply)


class LocalServer(Server):
    """
    Provide local methods to remote clients.

    Objects of this class associate a collection of method objects
    which are implemented by callback functions with a scope under
    which these methods are exposed for remote clients.

    .. codeauthor:: jmoringe
    """

    def __init__(self, scope, config):
        """
        Create a :obj:`LocalServer` that provides methods under a given scope.

        Args:
            scope (rsb.Scope):
                The scope under which the methods of the newly created server
                should be provided.
            config (rsb.ParticipantConfig):
                The transport configuration that should be used for
                communication performed by this server.

        See Also:
            :obj:`rsb.create_server`
        """
        super(LocalServer, self).__init__(scope, config)

    def add_method(self, name, func, request_type=object, reply_type=object,
                   allow_parallel_execution=False):
        """
        Add a method named ``name`` that is implemented by ``func``.

        Args:
            name (str):
                The name of of the new method.
            func:
                A callable object or a single argument that implements the
                desired behavior of the new method.
            request_type (types.TypeType):
                A type object indicating the type of request data passed to the
                method.
            reply_type:
                A type object indicating the type of reply data of the method.
            allow_parallel_execution(bool):
                if set to True, the method will be called fully asynchronously
                and even multiple calls may enter the method in parallel. Also,
                no ordering is guaranteed anymore.

        Returns:
            LocalMethod:
                The newly created method.
        """
        scope = self.scope.concat(rsb.Scope('/' + name))
        method = rsb.create_participant(
            LocalMethod, scope, self.config,
            parent=self,
            server=self,
            name=name,
            func=func,
            request_type=request_type,
            reply_type=reply_type,
            allow_parallel_execution=allow_parallel_execution)
        super(LocalServer, self).add_method(method)
        return method

    def remove_method(self, method):
        if isinstance(method, str):
            method = self.get_method(method)
        super(LocalServer, self).remove_method(method)

######################################################################
#
# Remote Server
#
######################################################################


class RemoteMethod(Method):
    """
    Represents a method provided by a remote server.

    Method objects are callable like regular bound method objects.

    .. codeauthor:: jmoringe
    """

    def __init__(self, scope, config, server, name, request_type, reply_type):
        super(RemoteMethod, self).__init__(scope, config,
                                           server, name,
                                           request_type, reply_type)

        self._calls = {}
        self._lock = threading.RLock()

    def make_listener(self):
        listener = rsb.create_listener(self.scope, self.config,
                                       parent=self)
        listener.add_filter(rsb.filter.MethodFilter(method='REPLY'))
        listener.add_handler(self._handle_reply)
        return listener

    def make_informer(self):
        return rsb.create_informer(self.scope, self.config,
                                   parent=self,
                                   data_type=self.request_type)

    def _handle_reply(self, event):
        if not event.causes:
            return

        key = event.causes[0]
        with self._lock:
            # We can receive reply events which aren't actually
            # intended for us. We ignore these.
            if key not in self._calls:
                return

            # The result future
            result = self._calls[key]
            del self._calls[key]
        if 'rsb:error?' in event.meta_data.user_infos:
            result.set_error(event.data)
        else:
            result.set_result(event)

    def __call__(self, arg=None, timeout=0):
        """
        Call the method synchronously and returns the results.

        Calls the represented method with argument ``arg``, returning
        the value returned by the remote method.

        If ``arg`` is an instance of :obj:`Event`, an :obj:`Event` containing
        the object returned by the remote method as payload is
        returned. If ``arg`` is of any other type, return the object
        that was returned by the remote method.

        The call to this method blocks until a result is available or
        an error occurs.

        Examples:
            >>> my_server.echo('bla')
            'bla'
            >>> my_server.echo(Event(scope=my_server.scope, data='bla',
            >>>                     type=str))
            Event[id = ..., data = 'bla', ...]

        Args:
            arg:
                The argument object that should be passed to the remote method.
                A converter has to be available for the type of ``arg``.
            timeout:
                The amount of time in seconds in which the operation has to
                complete.

        Returns:
            The object that was returned by the remote method.

        Raises:
            RemoteCallError:
                If invoking the remote method fails or the remote method itself
                produces an error.
            FutureTimeout
                If ``timeout`` is non-zero and the remote method does
                not respond within the specified time frame.

        See Also:
            :obj:`asynchronous`

        """
        return self.asynchronous(arg).get(timeout=timeout)

    def asynchronous(self, arg=None):
        """
        Call the method asynchronously and returns a :obj:`Future`.

        Calls the represented method with argument ``arg``, returning
        a :obj:`Future` instance that can be used to retrieve the result.

        If ``arg`` is an instance of :obj:`Event`, the result of the method
        call is an :obj:`Event` containing the object returned by the
        remote method as payload. If ``arg`` is of any other type, the
        result is the payload of the method call is the object that
        was returned by the remote method.

        The call to this method returns immediately, even if the
        remote method did produce a result yet. The returned :obj:`Future`
        instance has to be used to retrieve the result.

        Args:
            arg:
                The argument object that should be passed to the remote method.
                A converter has to be available for the type of ``arg``.

        Returns:
            Future or DataFuture:
                A :obj:`Future` or :obj:`DataFuture` instance that can be used
                to check the success of the method call, wait for the result
                and retrieve the result.

        Raises:
            RemoteCallError:
                If an error occurs before the remote was invoked.

        See Also:
            :obj:`__call__`

        Examples:
            >>> my_server.echo.asynchronous('bla')
            <Future running at 3054cd0>
            >>> my_server.echo.asynchronous('bla').get()
            'bla'
            >>> my_server.echo.asynchronous(Event(scope=my_server.scope,
            ...                           data='bla', type=str)).get()
            Event[id = ..., data = 'bla', ...]
        """
        self.listener  # Force listener creation

        # When the caller supplied an event, adjust the meta-data and
        # create a future that will return an event.
        if isinstance(arg, rsb.Event):
            event = arg
            event.scope = self.informer.scope
            event.method = 'REQUEST'
            result = Future()
        # Otherwise, create a new event with suitable meta-data and a
        # future that will return the payload of the reply event.
        else:
            event = rsb.Event(scope=self.informer.scope,
                              method='REQUEST',
                              data=arg,
                              data_type=type(arg))
            result = DataFuture()

        # Publish the constructed request event and record the call as
        # in-progress, waiting for a reply.
        try:
            with self._lock:
                event = self.informer.publish_event(event)
                self._calls[event.event_id] = result
        except Exception as e:
            raise RemoteCallError(self.server.scope, self, e) from e
        return result

    def __str__(self):
        return '<%s "%s" with %d in-progress calls at 0x%x>' \
            % (type(self).__name__, self.name, len(self._calls), id(self))

    def __repr__(self):
        return str(self)


class RemoteServer(Server):
    """
    Represents remote servers in a way that allows using normal methods calls.

    .. codeauthor:: jmoringe
    """

    def __init__(self, scope, config):
        """
        Create a new :obj:`RemoteServer` providing methods on the given scope.

        Args:
            scope (rsb.Scope):
                The common super-scope under which the methods of the remote
                created server are provided.
            config (rsb.ParticipantConfig):
                The configuration that should be used by this server.

        See Also:
            :obj:`rsb.create_remote_server`
        """
        super(RemoteServer, self).__init__(scope, config)

    def ensure_method(self, name):
        method = super(RemoteServer, self).get_method(name)
        if method is None:
            scope = self.scope.concat(rsb.Scope('/' + name))
            method = rsb.create_participant(RemoteMethod, scope, self.config,
                                            parent=self,
                                            server=self,
                                            name=name,
                                            request_type=object,
                                            reply_type=object)
            self.add_method(method)
        return method

    def get_method(self, name):
        return self.ensure_method(name)

    def __getattr__(self, name):
        # Treat missing attributes as methods.
        try:
            return super(RemoteServer, self).__getattr__(name)
        except AttributeError:
            return self.ensure_method(name)
