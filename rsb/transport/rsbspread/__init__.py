# ============================================================
#
# Copyright (C) 2010 by Johannes Wienke <jwienke at techfak dot uni-bielefeld dot de>
# Copyright (C) 2011-2018 Jan Moringen <jmoringe@techfak.uni-bielefeld.de>
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
This package contains a transport implementation based on the spread toolkit
which uses a multicased-based daemon network.

.. codeauthor:: jmoringe
.. codeauthor:: jwienke
"""

import threading
import uuid
import hashlib
import logging

import spread

import rsb
import rsb.util
import rsb.transport

from rsb.protocol.FragmentedNotification_pb2 import FragmentedNotification

import rsb.transport.conversion as conversion


def makeKey(notification):
    key = notification.event_id.sender_id + '%08x' \
        % notification.event_id.sequence_number
    return key


class Assembly(object):
    """
    A class that maintains a collection of fragments of one fragmented
    notification and assembles them if all fragments are received.

    .. codeauthor:: jwienke
    """

    def __init__(self, fragment):
        self.__requiredParts = fragment.num_data_parts
        assert(self.__requiredParts > 1)
        self.__id = makeKey(fragment.notification)
        self.__parts = {fragment.data_part: fragment}

    def add(self, fragment):
        key = makeKey(fragment.notification)
        assert(key == self.__id)
        if fragment.data_part in self.__parts:
            raise ValueError(
                "Received part %u for notification with id %s again."
                % (fragment.data_part, key))

        self.__parts[fragment.data_part] = fragment

        if len(self.__parts) == self.__requiredParts:
            return (self.__parts[0].notification, self.__join(),
                    self.__parts[0].notification.wire_schema)
        else:
            return None

    def __join(self):
        keys = self.__parts.keys()
        keys.sort()
        finalData = bytearray()
        for key in keys:
            finalData += bytearray(self.__parts[key].notification.data)
        return finalData


class AssemblyPool(object):
    """
    Maintains the parallel joining of notification fragments that are
    received in an interleaved fashion.

    .. codeauthor:: jwienke
    """

    def __init__(self):
        self.__assemblies = {}

    def add(self, fragment):
        notification = fragment.notification
        if fragment.num_data_parts == 1:
            return (notification, bytearray(notification.data),
                    notification.wire_schema)
        key = makeKey(notification)
        if key not in self.__assemblies:
            self.__assemblies[key] = Assembly(fragment)
            return None
        else:
            result = self.__assemblies[key].add(fragment)
            if result is not None:
                del self.__assemblies[key]
                return result


class SpreadConnection(object):
    """
    A wrapper around a Spread mailbox for some convenience.

    .. codeauthor:: jwienke
    .. codeauthor:: jmoringe
    """

    def __init__(self, daemonName, spreadModule=spread):
        self.__logger = rsb.util.getLoggerByClass(self.__class__)

        self.__daemonName = daemonName
        self.__spreadModule = spreadModule
        self.__mailbox = None

    def activate(self):
        if self.__mailbox is not None:
            raise ValueError("Already activated")
        self.__logger.info("Connecting to Spread daemon at '%s'",
                           self.__daemonName)
        self.__mailbox = self.__spreadModule.connect(self.__daemonName)

    def deactivate(self):
        if self.__mailbox is None:
            raise ValueError("Not activated")
        self.__logger.info("Disconnecting from Spread daemon at '%s'",
                           self.__daemonName)
        self.__mailbox.disconnect()
        self.__mailbox = None

    def join(self, group):
        self.__logger.info("Joining Spread group '%s'", group)
        self.__mailbox.join(group)

    def leave(self, group):
        self.__logger.info("Leaving Spread group '%s'", group)
        self.__mailbox.leave(group)

    def receive(self):
        return self.__mailbox.receive()

    def send(self, serviceType, groups, payload):
        self.__mailbox.multigroup_multicast(
            serviceType | spread.SELF_DISCARD, groups, payload)

    def interrupt(self, group):
        self.__logger.info("Interrupting receive calls using group '%s'",
                           group)
        self.__mailbox.multicast(spread.RELIABLE_MESS, group, "")

    def getHost(self):
        name = self.__daemonName.split('@')
        return name[1] if '@' in name else 'localhost'

    host = property(getHost)

    def getPort(self):
        return int(self.__daemonName.split('@')[0])

    port = property(getPort)


class RefCountingSpreadConnection(SpreadConnection):

    def __init__(self, daemonName, spreadModule=spread):
        SpreadConnection.__init__(self, daemonName, spreadModule=spreadModule)
        self.__lock = threading.RLock()
        self.__counter = 0

    def activate(self):
        with self.__lock:
            if self.__counter == 0:
                SpreadConnection.activate(self)
            self.__counter += 1

    def deactivate(self):
        with self.__lock:
            if self.__counter <= 0:
                raise ValueError("deactivate called more times than activate")
            self.__counter -= 1
            if self.__counter == 0:
                SpreadConnection.deactivate(self)


class DeserializingHandler(object):
    """
    Assembles notification fragments into complete Notifications.

    .. codeauthor:: jmoringe
    """
    def __init__(self):
        self.__logger = rsb.util.getLoggerByClass(self.__class__)

        self.__assemblyPool = AssemblyPool()

    def handleMessage(self, message):
        """
        Maybe returns notification extracted from `message`.

        If `message` is one part of a fragmented notification for
        which some parts are still pending, a complete notification
        cannot be constructed and ``None`` is returned.

        Args:
            message: The received Spread message.

        Returns:
            notification: The assembled notification or ``None``.
        """

        # Only handle regular messages.
        if not hasattr(message, 'msg_type'):
            return None

        fragment = FragmentedNotification()
        fragment.ParseFromString(message.message)

        self.__logger.debug(
            "Received notification fragment "
            "from bus (%s/%s), data length: %s",
            fragment.data_part,
            fragment.num_data_parts,
            len(fragment.notification.data))

        return self.__assemblyPool.add(fragment)


class SpreadReceiverTask(object):
    """
    Thread used to receive messages from a spread connection.

    .. codeauthor:: jwienke
    .. codeauthor:: jmoringe
    """

    def __init__(self, connection, observerAction):
        """
        Constructor.

        Args:
            connection:
                Spread connection to receive messages from.
            observerAction:
                Callable to invoke when a new event is received.
        """

        self.__logger = rsb.util.getLoggerByClass(self.__class__)

        self.__connection = connection
        # Spread groups are 32 chars long and 0-terminated.
        self.__wakeupGroup = str(uuid.uuid1()).replace("-", "")[:-1]

        self.__deserializingHandler = DeserializingHandler()

        self.__observerAction = observerAction

    def __call__(self):

        # Join "wakeup group" to receive interrupt messages.
        # receive() does have a timeout, hence we need a way to stop
        # receiving messages on interruption even if no one else sends
        # messages.  Otherwise deactivate would block until another
        # message is received.
        self.__logger.debug("Joining wakeup group %s", self.__wakeupGroup)
        self.__connection.join(self.__wakeupGroup)

        while True:

            self.__logger.debug("Waiting for messages")
            message = self.__connection.receive()
            self.__logger.debug("Received message %s", message)

            # Break out of receive loop if deactivating.
            if hasattr(message, 'msg_type') \
               and self.__wakeupGroup in message.groups:
                break

            try:
                notification \
                    = self.__deserializingHandler.handleMessage(message)
                self.__observerAction(notification)
            except Exception, e:
                self.__logger.exception("Error processing new event")
                raise e

        self.__connection.leave(self.__wakeupGroup)

    def interrupt(self):
        # send the interruption message to make the
        # __connection.receive() call in __call__ return.
        self.__connection.interrupt(self.__wakeupGroup)


class GroupNameCache(object):
    """
    Responsible for turning :ref:`scopes <scope>` into Spread group
    names.

    .. codeauthor:: jmoringe
    """
    def scopeToGroups(self, scope):
        scopes = scope.superScopes(True)
        return tuple(self.groupName(scope) for scope in scopes)

    @staticmethod
    def groupName(scope):
        hashSum = hashlib.md5()
        hashSum.update(scope.toString())
        return hashSum.hexdigest()[:-1]


class Memberships(object):
    """
    Reference counting-based management of Spread group membership.

    Not thread-safe.

    .. codeauthor:: jmoringe
    """

    def __init__(self, connection):
        self.__logger = rsb.util.getLoggerByClass(self.__class__)

        self.__connection = connection
        self.__groups = dict()

    def join(self, group):
        if group not in self.__groups:
            self.__logger.debug("Incrementing group '%s', 0 -> 1", group)
            self.__groups[group] = 1
            self.__connection.join(group)
        else:
            count = self.__groups[group]
            self.__logger.debug("Incrementing group '%s', %d -> %d",
                                group, count, count + 1)
            self.__groups[group] = count + 1

    def leave(self, group):
        count = self.__groups[group]
        self.__logger.debug("Decrementing group '%s', %d -> %d",
                            group, count, count - 1)
        if count == 1:
            del self.__groups[group]
            self.__connection.leave(group)
        else:
            self.__groups[group] = count - 1


class Connector(rsb.transport.Connector,
                rsb.transport.ConverterSelectingConnector):
    """
    Superclass for Spread-based connector classes. This class manages
    the direction-independent aspects like the Spread connection and
    (de)activation.

    .. codeauthor:: jwienke
    """

    MAX_MSG_LENGTH = 100000

    def __init__(self, connection, **kwargs):
        super(Connector, self).__init__(wireType=bytearray, **kwargs)

        self.__logger = rsb.util.getLoggerByClass(self.__class__)
        self.__connection = connection

        self.__active = False

    def __del__(self):
        if self.__active:
            self.deactivate()

    def setQualityOfServiceSpec(self, qos):
        pass

    def getConnection(self):
        return self.__connection

    connection = property(getConnection)

    def isActive(self):
        return self.__active

    active = property(isActive)

    def activate(self):
        if self.__active:
            raise RuntimeError('Trying to activate active Connector')

        self.__logger.info("Activating spread connector with connection %s",
                           self.__connection)

        try:
            self.__connection.activate()
        except Exception, e:
            raise RuntimeError('Could not connect SpreadConnection "%s": %s' %
                               (self.__connection, e))

        self.__active = True

    def deactivate(self):
        if not self.__active:
            raise RuntimeError('Trying to deactivate inactive Connector')

        self.__logger.info("Deactivating spread connector")

        self.__active = False

        self.__connection.deactivate()

        self.__logger.debug("SpreadConnector deactivated")

    def getTransportURL(self):
        return 'spread://' \
            + self.__connection.getHost()  \
            + ':' + str(self.__connection.getPort())


class InConnector(Connector):
    def __init__(self, **kwargs):
        super(InConnector, self).__init__(**kwargs)

        self.__scope = None
        self.__memberships = Memberships(self.connection)

    def setScope(self, scope):
        assert not self.active
        self.__scope = scope

    def activate(self):
        super(InConnector, self).activate()

        assert self.__scope is not None
        self.__memberships.join(GroupNameCache.groupName(self.__scope))

    def deactivate(self):
        self.__memberships.leave(GroupNameCache.groupName(self.__scope))

        super(InConnector, self).deactivate()

    def notificationToEvent(self, notification):
        if notification is None:
            return None

        notification, joinedData, wireSchema = notification

        # Create event from (potentially assembled) notification(s)
        converter = self.converterMap.getConverterForWireSchema(wireSchema)
        try:
            return conversion.notificationToEvent(
                notification, joinedData, wireSchema, converter)
        except Exception:
            __handleLogger.exception("Unable to decode event. "
                                     "Ignoring and continuing.")
            return None


class InPushConnector(InConnector,
                      rsb.transport.InPushConnector):
    def __init__(self, **kwargs):
        self.__logger = rsb.util.getLoggerByClass(self.__class__)

        self.__receiveThread = None
        self.__receiveTask = None

        self.__observerAction = None

        super(InPushConnector, self).__init__(**kwargs)

    def activate(self):
        super(InPushConnector, self).activate()

        self.__receiveTask = SpreadReceiverTask(self.connection,
                                                self._handleIncomingNotification)
        self.__receiveThread = threading.Thread(target=self.__receiveTask)
        self.__receiveThread.start()

    def deactivate(self):
        self.__receiveTask.interrupt()
        self.__receiveThread.join(timeout=1)
        self.__receiveThread = None
        self.__receiveTask = None

        super(InPushConnector, self).deactivate()

    def filterNotify(self, theFilter, action):
        self.__logger.debug("Ignoring filter %s with action %s",
                            theFilter, action)

    def setObserverAction(self, observerAction):
        self.__observerAction = observerAction

    def _handleIncomingNotification(self, notification):
        event = self.notificationToEvent(notification)
        if event is not None and self.__observerAction:
            self.__observerAction(event)


class InPullConnector(InConnector,
                      rsb.transport.InPullConnector):
    def __init__(self, **kwargs):
        super(InPullConnector, self).__init__(**kwargs)

        self.__logger = rsb.util.getLoggerByClass(self.__class__)

        self.__deserializingHandler = DeserializingHandler()

    def raiseEvent(self, block):
        self.__logger.debug("raiseEvent starts")

        event = None
        while event is None:
            self.__logger.debug("next loop iteration")
            if not block:
                if self.connection._SpreadConnection__mailbox.poll() <= 0:
                    return None

            message = self.connection.receive()
            if not hasattr(message, 'msg_type'):
                continue

            notification = self.__deserializingHandler.handleMessage(message)
            if notification is None:
                continue

            event = self.notificationToEvent(notification)

        self.__logger.debug("Receive loop exits")

        return event


class OutConnector(Connector,
                   rsb.transport.OutConnector):
    def __init__(self, **kwargs):
        self.__logger = rsb.util.getLoggerByClass(self.__class__)

        super(OutConnector, self).__init__(**kwargs)

        self.__groupNameCache = GroupNameCache()

        self.__serviceType = spread.FIFO_MESS

    def setQualityOfServiceSpec(self, qos):
        self.__serviceType = self.computeServiceType(qos)

    def handle(self, event):
        self.__logger.debug("Sending event: %s", event)

        if not self.active:
            self.__logger.warning("Connector not activated")
            return

        # Create one or more notification fragments for the event
        event.getMetaData().setSendTime()
        converter = self.getConverterForDataType(event.type)
        fragments = conversion.eventToNotifications(
            event, converter, self.MAX_MSG_LENGTH)

        # Send fragments
        self.__logger.debug("Sending %u fragments", len(fragments))
        for (i, fragment) in enumerate(fragments):
            serialized = fragment.SerializeToString()
            self.__logger.debug("Sending fragment %u of length %u",
                                i + 1, len(serialized))

            groupNames = self.__groupNameCache.scopeToGroups(event.scope)
            self.__logger.debug("Sending to groupNames %s", groupNames)

            sent = self.connection.send(self.__serviceType,
                                        groupNames,
                                        serialized)
            if (sent > 0):
                self.__logger.debug("Message sent successfully (bytes = %i)",
                                    sent)
            else:
                # TODO(jmoringe): propagate error
                self.__logger.warning(
                    "Error sending message, status code = %s", sent)

    def computeServiceType(self, qos):
        self.__logger.debug("Adapting service type for QoS %s", qos)

        if qos.getReliability() == rsb.QualityOfServiceSpec.Reliability.UNRELIABLE:
            if qos.getOrdering() == rsb.QualityOfServiceSpec.Ordering.UNORDERED:
                serviceType = spread.UNRELIABLE_MESS
            elif qos.getOrdering() == rsb.QualityOfServiceSpec.Ordering.ORDERED:
                serviceType = spread.FIFO_MESS
        elif qos.getReliability() == rsb.QualityOfServiceSpec.Reliability.RELIABLE:
            if qos.getOrdering() == rsb.QualityOfServiceSpec.Ordering.UNORDERED:
                serviceType = spread.RELIABLE_MESS
            elif qos.getOrdering() == rsb.QualityOfServiceSpec.Ordering.ORDERED:
                serviceType = spread.FIFO_MESS

        self.__logger.debug("Service type for %s is %s", qos, serviceType)
        return serviceType


class TransportFactory(rsb.transport.TransportFactory):
    """
    :obj:`TransportFactory` implementation for the spread transport.

    .. codeauthor:: jwienke
    """

    def __init__(self):
        self.__lock = threading.RLock()
        self.__connectionByDaemon = {}

    def getName(self):
        return "spread"

    def isRemote(self):
        return True

    @staticmethod
    def __createDaemonName(options):

        host = options.get('host', None)
        port = options.get('port', '4803')
        if host:
            return '%s@%s' % (port, host)
        else:
            return port

    def __getSharedConnection(self, daemonName):
        with self.__lock:
            if daemonName not in self.__connectionByDaemon:
                self.__connectionByDaemon[daemonName] = \
                    RefCountingSpreadConnection(daemonName)
            return self.__connectionByDaemon[daemonName]

    def createInPushConnector(self, converters, options):
        return InPushConnector(connection=SpreadConnection(
            self.__createDaemonName(options)), converters=converters)

    def createInPullConnector(self, converters, options):
        return InPullConnector(connection=SpreadConnection(
            self.__createDaemonName(options)), converters=converters)

    def createOutConnector(self, converters, options):
        return OutConnector(connection=self.__getSharedConnection(
            self.__createDaemonName(options)), converters=converters)


def initialize():
    try:
        rsb.transport.registerTransport(TransportFactory())
    except ValueError:
        pass
