# ============================================================
#
# Copyright (C) 2011-2018 Jan Moringen
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
Contains a transport based on point-to-point socket connections.

.. codeauthor:: jmoringe
"""

import copy
import socket
import threading

import rsb.eventprocessing
from rsb.protocol.Notification_pb2 import Notification
import rsb.transport
import rsb.transport.conversion as conversion
import rsb.util


class BusConnection(rsb.eventprocessing.BroadcastProcessor):
    """
    Implements a connection to a socket-based bus.

    The basic operations provided by this class are receiving an event by
    calling :obj:`receive_notification` and submitting an event to the bus by
    calling :obj:`send_notification`.

    In a process which act as a client for a particular bus, a single
    instance of this class is connected to the bus server and provides
    access to the bus for the process.

    A process which acts as the server for a particular bus, manages
    (via the :obj:`BusServer` class) one :obj:`BusConnection` object for each
    client (remote process) connected to the bus.

    .. codeauthor:: jmoringe

    Args:

    Returns:

    """

    def __init__(self,
                 host=None, port=None, socket_=None,
                 is_server=False, tcpnodelay=True):
        """
        Create a new instance.

        Args:
            host (str or None):
                Hostname or address of the bus server.
            port (int or None):
                Port of the bus server.
            socket_:
                A socket object through which the new connection should access
                the bus.
            is_server (bool):
                if True, the created object will perform the server part of the
                handshake protocol.
            tcpnodelay (bool):
                If True, the socket will be set to TCP_NODELAY.

        See Also:
            :obj:`get_bus_client_for`, :obj:`get_bus_server_for`.
        """
        super().__init__()

        self._logger = rsb.util.get_logger_by_class(self.__class__)

        self._thread = None
        self._socket = None

        self._error_hook = None

        self._active = False
        self._active_shutdown = False

        self._lock = threading.RLock()

        # Create a socket connection or store the provided connection.
        if host is not None and port is not None:
            if socket_ is None:
                self._socket = socket.create_connection((host, port))
            else:
                raise ValueError('Specify either host and port or socket')
        elif socket_ is not None:
            self._socket = socket_
        else:
            raise ValueError('Specify either host and port or socket_')
        if tcpnodelay:
            self._socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        else:
            self._socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 0)

        # Perform the client or server part of the handshake.
        if is_server:
            self._socket.send(b'\0\0\0\0')
        else:
            zero = self._socket.recv(4)
            if zero != b'\0\0\0\0':
                raise RuntimeError('Incorrect handshake')

    def __del__(self):
        if self._active:
            self.deactivate()

    @property
    def error_hook(self):
        return self._error_hook

    @error_hook.setter
    def error_hook(self, new_value):
        self._error_hook = new_value

    # receiving

    def receive_notification(self):
        size = self._socket.recv(4)
        if len(size) == 0:
            self._logger.info("Received EOF")
            raise EOFError()
        if not (len(size) == 4):
            raise RuntimeError('Short read when receiving notification size '
                               '(size: {})'.format(len(size)))
        size = size[0] | size[1] << 8 | size[2] << 16 | size[3] << 24
        self._logger.debug('Receiving notification of size %d', size)
        notification = self._socket.recv(size)
        if not (len(notification) == size):
            raise RuntimeError(
                'Short read when receiving notification payload')
        return notification

    @staticmethod
    def buffer_to_notification(serialized):
        notification = Notification()
        notification.ParseFromString(serialized)
        return notification

    def do_one_notification(self):
        serialized = self.receive_notification()
        notification = self.buffer_to_notification(serialized)
        self.dispatch(notification)

    def receive_notifications(self):
        while True:
            self._logger.debug('Receiving notifications')
            try:
                self.do_one_notification()
            except EOFError:
                self._logger.info("Received EOF while reading")
                if not self._active_shutdown:
                    self.shutdown()
                break
            except Exception as e:
                self._logger.warn('Receive error: %s', e, exc_info=True)
                if self.error_hook is not None:
                    self.error_hook(e)
                break
        return

    # sending

    def send_notification(self, notification):
        size = len(notification)
        self._logger.info('Sending notification of size %d', size)
        size = bytes([size & 0x000000ff,
                      (size & 0x0000ff00) >> 8,
                      (size & 0x00ff0000) >> 16,
                      (size & 0xff000000) >> 24])
        with self._lock:
            self._socket.send(size)
            self._socket.send(notification)

    @staticmethod
    def notification_to_buffer(notification):
        return notification.SerializeToString()

    def handle(self, notification):
        serialized = self.notification_to_buffer(notification)
        self.send_notification(serialized)

    # state management

    def activate(self):
        if self._active:
            raise RuntimeError('Trying to activate active connection')

        with self._lock:

            self._thread = threading.Thread(target=self.receive_notifications)
            self._thread.start()

            self._active = True

    def shutdown(self):
        with self._lock:
            self._active_shutdown = True
            self._socket.shutdown(socket.SHUT_WR)

    def deactivate(self):

        with self._lock:

            if not self._active:
                raise RuntimeError('Trying to deactivate inactive connection')

            self._active = False

            # If necessary, close the socket, this will cause an exception
            # in the notification receiver thread (unless we run in the
            # context that thread).
            self._logger.info('Closing socket')
            try:
                self._socket.close()
            except Exception as e:
                self._logger.warn('Failed to close socket: %s', e,
                                  exc_info=True)

    def wait_for_deactivation(self):
        self._logger.info('Joining thread')
        self._thread.join()


class Bus:
    """
    Instances of this class provide access to a socket-based bus.

    It is transparent for clients (connectors) of this class whether
    is accessed by running the bus server or by connecting to the bus
    server as a client.

    In-direction connectors add themselves as event sinks using the
    :obj:`add_connector` method.

    Out-direction connectors submit events to the bus using the
    :obj:`handle_outgoing` method.

    .. codeauthor:: jmoringe
    """

    def __init__(self):
        self._logger = rsb.util.get_logger_by_class(self.__class__)

        self._connections = []
        self._connectors = []
        self._dispatcher = rsb.eventprocessing.ScopeDispatcher()
        self._lock = threading.RLock()

        self._active = False

    @property
    def lock(self):
        return self._lock

    @property
    def connections(self):
        """
        Return the attached connections.

        Returns:
            list:
                A list of all connections to the bus.
        """
        return self._connections

    def add_connection(self, connection):
        """
        Add ``connection`` to the list of connections of this bus.

        This cause notifications send over this bus to be send through
        ``connection`` and notifications received via ``connection`` to be
        dispatched to connectors of this bus.

        Args:
            connection:
                The connection that should be added to this bus.
        """
        with self.lock:
            self._connections.append(connection)

            class Handler:

                def __init__(_self):  # noqa: N805
                    _self.bus = self

                def __call__(_self, notification):  # noqa: N805
                    self.handle_incoming((connection, notification))
            connection.add_handler(Handler())

            def remove_and_deactivate(exception):
                self.remove_connection(connection)
                try:
                    connection.deactivate()
                except Exception as e:
                    self._logger.warning(
                        "Error while deactivating connection %s: %s",
                        connection, e, exc_info=True)
            connection.error_hook = remove_and_deactivate
            connection.activate()

    def remove_connection(self, connection):
        """
        Remove ``connection`` from the list of connections of this bus.

        Args:
            connection:
                The connection that should be removed from this bus.
        """
        self._logger.info('Removing connection %s', connection)

        with self.lock:
            if connection in self._connections:
                self._connections.remove(connection)
                connection.remove_handler([h for h in connection.handlers
                                           if h.bus is self][0])

    @property
    def connectors(self):
        return self._connectors

    def add_connector(self, connector):
        """
        Add ``connector`` to the list of connectors of this bus.

        Depending on the direction of ``connector``, this causes
        ``connector`` to either receive or broadcast notifications via
        this bus.

        Args:
            connector:
                The connector that should be added to this bus.
        """
        self._logger.info('Adding connector %s', connector)
        with self.lock:
            if isinstance(connector, InPushConnector):
                self._dispatcher.add_sink(connector.scope, connector)
            self._connectors.append(connector)

    def remove_connector(self, connector):
        """
        Remove ``connector`` from the list of connectors of this bus.

        Args:
            connector:
                The connector that should be removed from this bus.
        """
        self._logger.info('Removing connector %s', connector)
        with self.lock:
            if isinstance(connector, InPushConnector):
                self._dispatcher.remove_sink(connector.scope, connector)
            self._connectors.remove(connector)
            if not self._connectors:
                self._logger.info(
                    'Removed last connector; requesting deletion')
                return False
            return True

    def handle_incoming(self, connection_and_notification):
        _, notification = connection_and_notification
        self._logger.debug('Trying to distribute notification to connectors')
        with self.lock:
            self._logger.debug(
                'Locked bus to distribute notification to connectors')
            if not self._active:
                self._logger.info(
                    'Cancelled distribution to connectors '
                    'since bus is not active')
                return

            # Distribute the notification to participants in our
            # process via InPushConnector instances.
            self._to_connectors(notification)

    def handle_outgoing(self, notification):
        with self.lock:
            self._logger.debug('Locked bus to distribute notification to '
                               'connections and connectors')
            if not self._active:
                self._logger.info('Cancelled distribution to connections '
                                  'and connectors since bus is not active')
                return

            # Distribute the notification to remote participants via
            # network connections.
            failing = self._to_connections(notification)
            # Distribute the notification to participants in our own
            # process via InPushConnector instances.
            self._to_connectors(notification)
        # there are only failing connection in case of an unorderly shutdown.
        # So the shutdown protocol does not apply here and
        # we can immediately call deactivate.
        list(map(BusConnection.deactivate, failing))

    # State management

    @property
    def active(self):
        return self._active

    def activate(self):
        if self._active:
            raise RuntimeError('Trying to activate active bus')

        with self.lock:
            self._active = True

    def deactivate(self):
        if not self._active:
            raise RuntimeError('Trying to deactivate inactive bus')

        with self.lock:
            self._active = False
            connections_copy = copy.copy(self.connections)

        # We do not have to lock the bus here, since
        # 1) remove_connection will do that for each connection
        # 2) the connection list will not be modified concurrently at
        #    this point
        self._logger.info('Closing connections')
        for connection in connections_copy:
            try:
                self.remove_connection(connection)
                connection.shutdown()
                connection.wait_for_deactivation()
            except Exception as e:
                self._logger.error('Failed to close connections: %s', e,
                                   exc_info=True)

    # Low-level helpers

    def _to_connections(self, notification, exclude=None):
        failing = []
        for connection in self.connections:
            if connection is not exclude:
                try:
                    connection.handle(notification)
                except Exception as e:
                    self._logger.warn(
                        'Failed to send to %s: %s; '
                        'will close connection later',
                        connection, e, exc_info=True)
                    failing.append(connection)

        # Removed connections for which sending the notification
        # failed.
        list(map(self.remove_connection, failing))
        return failing

    def _to_connectors(self, notification):
        # Deliver NOTIFICATION to connectors which fulfill two
        # criteria:
        # 1) Direction has to be "incoming events"
        # 2) The scope of the connector has to be a superscope of
        #    NOTIFICATION's scope
        scope = rsb.Scope(notification.scope.decode('ASCII'))
        for sink in self._dispatcher.matching_sinks(scope):
            sink.handle(notification)

    def __repr__(self):
        return '<{} {} connection(s) {} connector(s) at 0x{:x}>'.format(
            type(self).__name__, len(self.connections),
            len(self.connectors), id(self))


_bus_clients = {}
_bus_clients_lock = threading.Lock()


def get_bus_client_for(host, port, tcpnodelay, connector):
    """
    Return a bus client for the given end point and attach a connector to it.

    Return (creating it if necessary), a :obj:`BusClient` for the endpoint
    designated by ``host`` and ``port`` and attach ``connector`` to
    it. Attaching ``connector`` marks the bus client as being in use
    and protects it from being destroyed in a race condition
    situation.

    Args:
        host (str):
            A hostname or address of the node on which the bus server listens.
        port (int):
            The port on which the bus server listens.
        tcpnodelay (bool):
            If True, the socket will be set to TCP_NODELAY.
        connector:
            A connector that should be attached to the bus client.
    """
    key = (host, port, tcpnodelay)
    with _bus_clients_lock:
        bus = _bus_clients.get(key)
        if bus is None:
            bus = BusClient(host, port, tcpnodelay)
            _bus_clients[key] = bus
            bus.activate()
            bus.add_connector(connector)
        else:
            bus.add_connector(connector)
        return bus


class BusClient(Bus):
    """
    Provides access to a bus by means of a client socket.

    .. codeauthor:: jmoringe
    """

    def __init__(self, host, port, tcpnodelay):
        """
        Create a new client connection on the specified host and port.

        Args:
            host (str):
                A hostname or address of the node on which the bus server
                listens.
            port (int):
                The port on which the new bus server listens.
            tcpnodelay (bool):
                If True, the socket will be set to TCP_NODELAY.
        """
        super().__init__()

        self.add_connection(BusConnection(host, port, tcpnodelay=tcpnodelay))


_bus_servers = {}
_bus_servers_lock = threading.Lock()


def get_bus_server_for(host, port, tcpnodelay, connector):
    """
    Return a bus server for the given end point and attach a connector to it.

    Return (creating it if necessary), a :obj:`BusServer` for the endpoint
    designated by ``host`` and ``port`` and attach ``connector`` to
    it. Attaching ``connector`` marks the bus server as being in use
    and protects it from being destroyed in a race condition
    situation.

    Args:
        host (str):
            A hostname or address identifying the interface to which the listen
            socket of the new bus server should be bound.
        port (int):
            The port to which the listen socket of the new bus server should be
            bound.
        tcpnodelay (bool):
            If True, the socket will be set to TCP_NODELAY.
        connector:
            A connector that should be attached to the bus server.
    """
    key = (host, port, tcpnodelay)
    with _bus_servers_lock:
        bus = _bus_servers.get(key)
        if bus is None:
            bus = BusServer(host, port, tcpnodelay)
            bus.activate()
            _bus_servers[key] = bus
            bus.add_connector(connector)
        else:
            bus.add_connector(connector)
        return bus


class BusServer(Bus):
    """
    Provides access to a socket-based bus for local and remote bus clients.

    Remote clients can connect to a server socket in order to send and
    receive events through the resulting socket connection.

    Local clients (connectors) use the usual :obj:`Bus` interface to
    receive events submitted by remote clients and submit events which
    will be distributed to remote clients by the :obj:`BusServer`.

    .. codeauthor:: jmoringe
    """

    def __init__(self, host, port, tcpnodelay, backlog=5):
        """
        Create a new instance on the given host and port.

        Args:
            host (str):
                A hostname or address identifying the interface to which the
                listen socket of the new bus server should be bound.
            port (int):
                The port to which the listen socket of the new bus server
                should be bound.
            tcpnodelay (bool):
                If True, the socket will be set to TCP_NODELAY.
            backlog (int):
                The maximum number of queued connection attempts.
        """
        super().__init__()

        self._logger = rsb.util.get_logger_by_class(self.__class__)

        self._host = host
        self._port = port
        self._tcpnodelay = tcpnodelay
        self._backlog = backlog
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._acceptor_thread = None

    def __del__(self):
        if self.active:
            self.deactivate()

    def accept_clients(self):
        import sys
        if sys.platform == 'darwin':
            self._socket.settimeout(1.0)
        while self._socket:
            self._logger.info('Waiting for clients')
            try:
                client_socket, addr = self._socket.accept()
                if sys.platform == 'darwin':
                    client_socket.settimeout(None)
                self._logger.info('Accepted client %s', addr)
                self.add_connection(
                    BusConnection(socket_=client_socket,
                                  is_server=True,
                                  tcpnodelay=self._tcpnodelay))
            except socket.timeout as e:
                if sys.platform != 'darwin':
                    self._logger.error(
                        'Unexpected timeout in accept_clients: "%s"', e,
                        exc_info=True)
            except Exception as e:
                if self.active:
                    self._logger.error('Exception in accept_clients: "%s"', e,
                                       exc_info=True)
                else:
                    self._logger.info('Acceptor thread terminating')

    # Receiving notifications

    def handle_incoming(self, connection_and_notification):
        super().handle_incoming(connection_and_notification)

        # Distribute the notification to all connections except the
        # one that sent it.
        (sending_connection, notification) = connection_and_notification
        with self.lock:
            self._to_connections(notification, exclude=sending_connection)

    # State management

    def activate(self):
        super().activate()

        # Bind the socket and start listening
        self._logger.info('Opening listen socket %s:%d',
                          '0.0.0.0', self._port)
        self._socket.bind(('0.0.0.0', self._port))
        self._socket.listen(self._backlog)

        self._logger.info('Starting acceptor thread')
        self._acceptor_thread = threading.Thread(target=self.accept_clients)
        self._acceptor_thread.start()

    def deactivate(self):
        if not self.active:
            raise RuntimeError('Trying to deactivate inactive BusServer')

        # If necessary, close the listening socket. This causes an
        # exception in the acceptor thread.
        self._logger.info('Closing listen socket')
        if self._socket is not None:
            try:
                self._socket.shutdown(socket.SHUT_RDWR)
            except Exception as e:
                self._logger.warn('Failed to shutdown listen socket: %s', e,
                                  exc_info=True)
            try:
                self._socket.close()
            except Exception as e:
                self._logger.warn('Failed to close listen socket: %s', e,
                                  exc_info=True)
            self._socket = None

        # The acceptor thread should encounter an exception and exit
        # eventually. We wait for that.
        self._logger.info('Waiting for acceptor thread')
        if self._acceptor_thread is not None:
            self._acceptor_thread.join()

        super().deactivate()


def remove_connector(bus, connector):
    def remove_and_maybe_kill(lock, dictionary):
        with lock:
            if not bus.remove_connector(connector):
                bus.deactivate()
                del dictionary[[key
                                for (key, value) in list(dictionary.items())
                                if value is bus][0]]

    if isinstance(bus, BusClient):
        remove_and_maybe_kill(_bus_clients_lock, _bus_clients)
    else:
        remove_and_maybe_kill(_bus_servers_lock, _bus_servers)


class Connector(rsb.transport.Connector,
                rsb.transport.ConverterSelectingConnector):
    """
    Base class for connectors that operate on a socket connection based bus.

    Instances of subclasses of this class receive events from a bus
    (represented by a :obj:`Bus` object) that is accessed via a socket
    connection.

    .. codeauthor:: jmoringe
    """

    def __init__(self, converters, options=None, **kwargs):
        super().__init__(wire_type=bytes, converters=converters, **kwargs)
        self._logger = rsb.util.get_logger_by_class(self.__class__)

        if options is None:
            options = {}

        self._active = False

        self._bus = None
        self._host = options.get('host', 'localhost')
        self._port = int(options.get('port', '55555'))
        self._tcpnodelay = options.get('nodelay', '1') in ['1', 'true']
        server_string = options.get('server', 'auto')
        if server_string in ['1', 'true']:
            self._server = True
        elif server_string in ['0', 'false']:
            self._server = False
        elif server_string == 'auto':
            self._server = 'auto'
        else:
            raise TypeError(
                'Server option has to be "1", "true", "0", "false" '
                'or "auto", not "{}"'.format(server_string))

    def __del__(self):
        if self._active:
            self.deactivate()

    def _get_bus(self, host, port, tcpnodelay, server):
        self._logger.info('Requested server role: %s', server)

        if server is True:
            self._logger.info('Getting bus server %s:%d', host, port)
            self._bus = get_bus_server_for(host, port, tcpnodelay, self)
        elif server is False:
            self._logger.info('Getting bus client %s:%d', host, port)
            self._bus = get_bus_client_for(host, port, tcpnodelay, self)
        elif server == 'auto':
            try:
                self._logger.info(
                    'Trying to get bus server %s:%d (in server = auto mode)',
                    host, port)
                self._bus = get_bus_server_for(host, port, tcpnodelay, self)
            except Exception as e:
                self._logger.info('Failed to get bus server: %s', e,
                                  exc_info=True)
                self._logger.info(
                    'Trying to get bus client %s:%d (in server = auto mode)',
                    host, port)
                self._bus = get_bus_client_for(host, port, tcpnodelay, self)
        else:
            raise TypeError(
                'Server argument has to be True, False or '
                '"auto", not "{}"'.format(server))
        self._logger.info('Got %s', self._bus)
        return self._bus

    @property
    def bus(self):
        return self._bus

    def activate(self):
        if self._active:
            raise RuntimeError('Trying to activate active connector')

        self._logger.info('Activating')

        self._bus = self._get_bus(self._host,
                                  self._port,
                                  self._tcpnodelay,
                                  self._server)

        self._active = True

    def deactivate(self):
        if not self._active:
            raise RuntimeError('Trying to deactivate inactive connector')

        self._logger.info('Deactivating')

        self._active = False

        remove_connector(self.bus, self)

    def set_quality_of_service_spec(self, qos):
        pass

    def get_transport_url(self):
        query = '?tcpnodelay=' + ('1' if self._tcpnodelay else '0')
        return 'socket://' + self._host + ':' + str(self._port) + query


class InPushConnector(Connector,
                      rsb.transport.InPushConnector):
    """
    Receives events from a bus represented by a socket connection.

    Instances of this class receive events from a bus (represented by
    a :obj:`Bus` object) that is accessed via a socket connection.

    The receiving and dispatching of events is done in push mode: each
    instance has a :obj:`Bus` which pushes appropriate events into the
    instance. The connector deserializes event payloads and pushes the
    events into handlers (usually objects which implement some event
    processing strategy).

    .. codeauthor:: jmoringe
    """

    def __init__(self, **kwargs):
        self._action = None

        super().__init__(**kwargs)

    def filter_notify(self, the_filter, action):
        pass

    def set_observer_action(self, action):
        self._action = action

    def handle(self, notification):
        if self._action is None:
            return

        converter = self.get_converter_for_wire_schema(
            notification.wire_schema.decode('ASCII'))
        event = conversion.notification_to_event(
            notification,
            wire_data=bytes(notification.data),
            wire_schema=notification.wire_schema.decode('ASCII'),
            converter=converter)
        self._action(event)


class OutConnector(Connector,
                   rsb.transport.OutConnector):
    """
    Sends events to a bus realized as a socket connection.

    Instance of this class send events to a bus (represented by a
    :obj:`Bus` object) that is accessed via a socket connection.

    .. codeauthor:: jmoringe
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def handle(self, event):
        # Create a notification fragment for the event and send it
        # over the bus.
        event.meta_data.send_time = None
        converter = self.get_converter_for_data_type(event.data_type)
        wire_data, wire_schema = converter.serialize(event.data)
        notification = Notification()
        conversion.event_to_notification(notification, event,
                                         wire_schema=wire_schema,
                                         data=wire_data)
        self.bus.handle_outgoing(notification)


class TransportFactory(rsb.transport.TransportFactory):
    """
    :obj:`TransportFactory` implementation for the socket transport.

    .. codeauthor:: jwienke
    """

    @property
    def name(self):
        return "socket"

    @property
    def remote(self):
        return True

    def create_in_push_connector(self, converters, options):
        return InPushConnector(converters=converters, options=options)

    def create_in_pull_connector(self, converters, options):
        raise NotImplementedError()

    def create_out_connector(self, converters, options):
        return OutConnector(converters=converters, options=options)


def initialize():
    try:
        rsb.transport.register_transport(TransportFactory())
    except ValueError:
        pass
