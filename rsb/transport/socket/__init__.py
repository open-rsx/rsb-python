# ============================================================
#
# Copyright (C) 2011 Jan Moringen <jmoringe@techfak.uni-bielefeld.de>
#
# This file may be licensed under the terms of of the
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

import socket
import threading

import rsb.transport

from rsb.protocol.EventId_pb2 import EventId
from rsb.protocol.EventMetaData_pb2 import UserInfo, UserTime
from rsb.protocol.Notification_pb2 import Notification

class BusConnection (rsb.eventprocessing.BroadcastProcessor):
    """
    Instances of this class implement connections to a socket-based
    bus.

    The basic operations provided by this class are receiving an event
    by calling L{receiveEvent} and submitting an event to the bus by
    calling L{sendEvent}.

    In a process which act as a client for a particular bus, a single
    instance of this class is connected to the bus server and provides
    access to the bus for the process.

    A process which acts as the server for a particular bus, manages
    (via the L{BusServer} class) one L{BusConnection} object for each
    client (remote process) connected to the bus.

    @author: jmoringe
    """

    def __init__(self, host = None, port = None, socket_ = None):
        """
        @param host: Hostname or address of the bus server.
        @type host: str or None
        @param port: Port of the bus server.
        @type port: int or None
        @param socket_: A socket object through which the new
                        connection should access the bus.

        See: L{getBusClientFor}, L{getBusServerFor}.
        """
        if not host is None and not port is None:
            if socket_ is None:
                self.__socket = socket.create_connection((host, port))
            else:
                raise ValueError, 'specify either host and port or socket'
        elif not socket is None:
            self.__socket = socket_
        else:
            raise ValueError, 'specify either host and port or socket'
        self.__file = self.__socket.makefile()

    # receiving

    def receiveNotification(self):
        size = self.__file.read(size = 4)
        size = ord(size[0])      \
            | ord(size[1]) << 8  \
            | ord(size[2]) << 16 \
            | ord(size[3]) << 24
        notification = self.__file.read(size = size)
        return notification

    def bufferToNotification(self, serialized):
        notification = Notification()
        notification.ParseFromString(serialized)
        return notification

    def doOneNotification(self):
        serialized = self.receiveNotification()
        notification = self.bufferToNotification(serialized)
        self.dispatch(notification)

    def receiveNotifications(self):
        while True:
            self.doOneNotification()

    # sending

    def sendNotification(self, notification):
        size = len(notification)
        size = ''.join((chr(size & 0x000000ff),
                        chr((size & 0x0000ff00) >> 8),
                        chr((size & 0x00ff0000) >> 16),
                        chr((size & 0xff000000) >> 24)))
        self.__file.write(size)
        self.__file.write(notification)

    def notificationToBuffer(self, notification):
        return notification.SerializeToString()

    def handle(self, notification):
        serialized = self.notificationToBuffer(notification)
        self.sendNotification(serialized)

    # state management

    def close(self):
        self.__file.close()
        self.__socket.close()

class Bus (object):
    """
    Instances of this class provide access to a socket-based bus.

    It is transparent for clients (connectors) of this class whether
    is accessed by running the bus server or by connecting to the bus
    server as a client.

    In-direction connectors add themselves as event sinks using the
    L{addConnector} method.

    Out-direction connectors submit events to the bus using the
    L{handle} method.

    @author: jmoringe
    """
    def __init__(self):
        self.__connections = []
        self.__connectors  = []
        self.__lock        = threading.Lock()

    def getConnections(self):
        """
        @return: A list of all connections to the bus.
        @rtype: list
        """
        return self.__connections

    def addConnection(self, connection):
        """
        Add B{connection} to the list of connections of this bus. This
        cause notifications send over this bus to be send through
        B{connection} and notifications received via B{connection} to
        be dispatched to connectors of this bus.

        @param connection: The connection that should be added to this
                           bus.
        """
        with self.__lock:
            self.__connections.append(connection)

    def removeConnection(self, connection):
        """
        @param connection:
        """
        with self.__lock:
            self.__connections.remove(connection)

    connections = property(getConnections)

    def getConnectors(self):
        with self.__lock:
            return self.__connectors

    def addConnector(self, connector):
        """
        Add B{connector} to the list of connectors of this
        bus. Depending on the direction of B{connector}, this causes
        B{connector} to either receive or broadcast notifications via
        this bus.

        @param connector: The connector that should be added to this
                          bus.
        """
        with self.__lock:
            self.__connectors.append(connector)

    def removeConnector(self, connector):
        with self.__lock:
            self.__connectors.remove(connector)
            if not self.__connectors:
                pass # TODO last remaining connector removed, destroy the bus

    connectors = property(getConnectors)

    def publish(self, event):
        raise NotImplementedError

    def __repr__(self):
        return '<%s %d conns %d cntors at 0x%x>' \
            % (type(self).__name__,
               len(self.getConnections()),
               len(self.getConnectors()),
               id(self))

__busClients = {}
__busClientsLock = threading.Lock()

def getBusClientFor(host, port, connector):
    """
    Return (creating it if necessary), a L{BusClient} for the endpoint
    designated by B{host} and B{port} and attach B{connector} to
    it. Attaching B{connector} marks the bus client as being in use
    and protects it from being destroyed in a race condition
    situation.

    @param host: A hostname or address of the node on which the bus
                 server listens.
    @type host: str
    @param port: The port on which the new bus server listens.
    @type port: int
    @param connector: A connector that should be attached to the bus
                      client.
    """
    key = (host, port)
    with __busClientsLock:
        bus = __busClients.get(key)
        if bus is None:
            bus = BusClient(host, port)
            __busClients[key] = bus
            bus.addConnector(connector)
        else:
            # TODO lock bus
            bus.addConnector(connector)
        return bus

class BusClient (Bus):
    """
    Instances of this class provide access to a bus by means of a
    client socket.

    @author: jmoringe
    """
    def __init__(self, host, port):
        """
        @param host: A hostname or address of the node on which the
                     bus server listens.
        @type host: str
        @param port: The port on which the new bus server listens.
        @type port: int
        """
        super(BusClient, self).__init__()

        self.addConnection(BusConnection(host, port))

__busServers = {}
__busServersLock = threading.Lock()

def getBusServerFor(host, port, connector):
    """
    Return (creating it if necessary), a L{BusServer} for the endpoint
    designated by B{host} and B{port} and attach B{connector} to
    it. Attaching B{connector} marks the bus server as being in use
    and protects it from being destroyed in a race condition
    situation.

    @param host: A hostname or address identifying the interface to
                 which the listen socket of the new bus server should
                 be bound.
    @type host: str
    @param port: The port to which the listen socket of the new bus
                 server should be bound.
    @type port: int
    @param connector: A connector that should be attached to the bus
                      server.
    """
    key = (host, port)
    with __busServersLock:
        bus = __busServers.get(key)
        if bus is None:
            bus = BusServer(host, port)
            __busServers[key] = bus
            bus.addConnector(connector)
        else:
            # TODO lock bus here
            bus.addConnector(connector)
        return bus

class BusServer (Bus):
    """
    Instances of this class provide access to a socket-based bus for
    local and remote bus clients.

    Remote clients can connect to a server socket in order to send and
    receive events through the resulting socket connection.

    Local clients (connectors) use the usual L{Bus} interface to
    receive events submitted by remote clients and submit events which
    will be distributed to remote clients by the L{BusServer}.

    @author: jmoringe
    """

    def __init__(self, host, port, backlog = 5):
        """
        @param host: A hostname or address identifying the interface
                     to which the listen socket of the new bus server
                     should be bound.
        @type host: str
        @param port: The port to which the listen socket of the new
                     bus server should be bound.
        @type port: int
        @param backlog: The maximum number of queued connection
                        attempts.
        @type backlog: int
        """
        super(BusServer, self).__init__()

        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__socket.bind((host, port))
        self.__socket.listen(backlog)

    def acceptClients(self):
        while True:
            socket, addr = self.__socket.accept()
            log('Connection from %s', addr)
            self.addConnection(BucConnection(socket = socket))

class Connector(rsb.transport.Connector,
                rsb.transport.ConverterSelectingConnector):
    """
    Instances of subclasses of this class receive events from a bus
    (represented by a L{Bus} object) that is accessed via a socket
    connection.

    @author: jmoringe
    """

    def __init__(self, host, port, server, **kwargs):
        super(Connector, self).__init__(wireType = bytes, **kwargs)

        # TODO(jmoringe): do this when activating?
        if server:
            self.__bus = getBusServerFor(host, port, self)
        else:
            self.__bus = getBusClientFor(host, port, self)

    def getBus(self):
        return self.__bus

    bus = property(getBus)

    def activate(self):
        pass

    def deactivate(self):
        pass

class InPushConnector (Connector,
                       rsb.transport.InConnector):
    """
    Instances of this class receive events from a bus (represented by
    a L{Bus} object) that is accessed via a socket connection.

    The receiving and dispatching of events is done in push mode: each
    instance has a L{Bus} which pushes appropriate events into the
    instance. The connector deserializes event payloads and pushes the
    events into handlers (usually objects which implement some event
    processing strategy).

    @author: jmoringe
    """

    def __init__(self, **kwargs):
        self.__action = None

        super(InPushConnector, self).__init__(**kwargs)

    def filterNotify(self, filter, action):
        pass

    def setObserverAction(self, action):
        self.__action = action

class OutConnector (Connector,
                    rsb.transport.OutConnector):
    def publish(self, event):
        self.bus.publish(event)
