# ============================================================
#
# Copyright (C) 2010 by Johannes Wienke <jwienke at techfak dot uni-bielefeld dot de>
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
This package contains a transport implementation based on the spread toolkit
which uses a multicased-based daemon network.

@author: jmoringe
@author: jwienke
"""

import threading
from threading import RLock
import uuid
import hashlib
import math
import logging
import time

import spread

import rsb
import rsb.util
import rsb.filter
import rsb.transport
import rsb.converter

from rsb.protocol.FragmentedNotification_pb2 import FragmentedNotification
from google.protobuf.message import DecodeError

import rsb.transport.conversion as conversion

def makeKey(notification):
    key = notification.event_id.sender_id + '%08x' % notification.event_id.sequence_number
    return key

class Assembly(object):
    """
    A class that maintains a collection of fragments of one fragmented
    notification and assembles them if all fragments are received.

    @author: jwienke
    """

    def __init__(self, fragment):
        self.__requiredParts = fragment.num_data_parts
        assert(self.__requiredParts > 1)
        self.__id    = makeKey(fragment.notification)
        self.__parts = {fragment.data_part : fragment}

    def add(self, fragment):
        key = makeKey(fragment.notification)
        assert(key == self.__id)
        if fragment.data_part in self.__parts:
            raise ValueError("Received part %u for notification with id %s again." % (fragment.data_part, key))

        self.__parts[fragment.data_part] = fragment

        if len(self.__parts) == self.__requiredParts:
            return self.__parts[0].notification, self.__join(), self.__parts[0].notification.wire_schema
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

    @author: jwienke
    """

    def __init__(self):
        self.__assemblies = {}

    def add(self, fragment):
        notification = fragment.notification
        if fragment.num_data_parts == 1:
            return notification, bytearray(notification.data), notification.wire_schema
        key = makeKey(notification)
        if not key in self.__assemblies:
            self.__assemblies[key] = Assembly(fragment)
            return None
        else:
            result = self.__assemblies[key].add(fragment)
            if result != None:
                del self.__assemblies[key]
                return result

class SpreadReceiverTask(object):
    """
    Thread used to receive messages from a spread connection.

    @author: jwienke
    """

    def __init__(self, mailbox, observerAction, converterMap):
        """
        Constructor.

        @param mailbox: spread mailbox to receive from
        @param observerAction: callable to execute if a new event is received
        @param converterMap: converters for data
        """

        self.__logger = rsb.util.getLoggerByClass(self.__class__)

        self.__interrupted = False
        self.__interruptionLock = threading.RLock()

        self.__mailbox = mailbox
        self.__observerAction = observerAction
        self.__observerActionLock = RLock()

        self.__converterMap = converterMap
        assert(converterMap.getWireType() == bytearray)

        self.__taskId = uuid.uuid1()
        # narf, spread groups are 32 chars long but 0-terminated... truncate id
        self.__wakeupGroup = str(self.__taskId).replace("-", "")[:-1]

        self.__assemblyPool = AssemblyPool()

    def __call__(self):

        # join my id to receive interrupt messages.
        # receive cannot have a timeout, hence we need a way to stop receiving
        # messages on interruption even if no one else sends messages.
        # Otherwise deactivate blocks until another message is received.
        self.__mailbox.join(self.__wakeupGroup)
        self.__logger.debug("joined wakup group %s", self.__wakeupGroup)

        while True:

            # check interruption
            self.__interruptionLock.acquire()
            interrupted = self.__interrupted
            self.__interruptionLock.release()

            if interrupted:
                break

            self.__logger.debug("waiting for new messages")
            message = self.__mailbox.receive()
            self.__logger.debug("received message %s", message)
            try:

                # Process regular message
                if isinstance(message, spread.RegularMsgType):
                    # ignore the deactivate wakeup message
                    if self.__wakeupGroup in message.groups:
                        continue

                    fragment = FragmentedNotification()
                    fragment.ParseFromString(message.message)

                    if self.__logger.isEnabledFor(logging.DEBUG):
                        data = str(fragment)
                        if len(data) > 5000:
                            data = data[:5000] + " [... truncated for printing]"
                        self.__logger.debug("Received notification fragment from bus: %s", data)

                    assembled = self.__assemblyPool.add(fragment)
                    if assembled:
                        notification, joinedData, wireSchema = assembled
                        # Create event from (potentially assembled)
                        # notification(s)
                        converter = self.__converterMap.getConverterForWireSchema(wireSchema)
                        event = conversion.notificationToEvent(notification, joinedData, wireSchema, converter)

                        self.__logger.debug("Sending event to dispatch task: %s", event)

                        with self.__observerActionLock:
                            if self.__observerAction:
                                self.__observerAction(event)

                # Process membership message
                elif isinstance(message, spread.MembershipMsgType):
                    self.__logger.info("Received membership message for group `%s'", message.group)

            except rsb.converter.UnknownConverterError, e:
                self.__logger.exception("Unable to deserialize message: %s", e)
            except DecodeError, e:
                self.__logger.exception("Error decoding notification: %s", e)
            except Exception, e:
                self.__logger.exception("Error decoding notification: %s", e)
                raise e

        # leave task id group to clean up
        self.__mailbox.leave(self.__wakeupGroup)

    def interrupt(self):
        self.__interruptionLock.acquire()
        self.__interrupted = True
        self.__interruptionLock.release()

        # send the interruption message to wake up receive as mentioned above
        self.__mailbox.multicast(spread.RELIABLE_MESS, self.__wakeupGroup, "")

    def setObserverAction(self, action):
        with self.__observerActionLock:
            self.__observerAction = action

class Connector(rsb.transport.Connector,
                rsb.transport.ConverterSelectingConnector):
    """
    Superclass for Spread-based connector classes. This class manages
    the direction-independent aspects like the Spread connection and
    (de)activation.

    @author: jwienke
    """

    MAX_MSG_LENGTH = 100000

    def __init__(self, options = {}, spreadModule = spread, **kwargs):
        super(Connector, self).__init__(wireType = bytearray, **kwargs)

        self.__logger = rsb.util.getLoggerByClass(self.__class__)

        host = options.get('host', None)
        port = options.get('port', '4803')
        if host:
            self.__daemonName = '%s@%s' % (port, host)
        else:
            self.__daemonName = port
        self.__connection   = None
        self.__spreadModule = spreadModule

        self.__active = False

        self.setQualityOfServiceSpec(rsb.QualityOfServiceSpec())

    def __del__(self):
        if self.__active:
            self.deactivate()

    def getConnection(self):
        return self.__connection

    connection = property(getConnection)

    def _getMsgType(self):
        return self.__msgType

    _msgType = property(_getMsgType)

    def activate(self):
        if self.__active:
            raise RuntimeError, 'Trying to activate active Connector'

        self.__logger.info("Activating spread connector with daemon name %s", self.__daemonName)

        try:
            self.__connection = self.__spreadModule.connect(self.__daemonName)
        except Exception, e:
            raise RuntimeError, 'could not connect to Spread daemon "%s": %s' % (self.__daemonName, e)

        self.__active = True

    def deactivate(self):
        if not self.__active:
            raise RuntimeError, 'Trying to deactivate inactive Connector'

        self.__logger.info("Deactivating spread connector")

        self.__active = False

        if not self.__connection is None:
            self.__connection.disconnect()
            self.__connection = None

        self.__logger.debug("SpreadConnector deactivated")

    def _groupName(self, scope):
        sum = hashlib.md5()
        sum.update(scope.toString())
        return sum.hexdigest()[:-1]

    def setQualityOfServiceSpec(self, qos):
        self.__logger.debug("Adapting service type for QoS %s", qos)
        if qos.getReliability() == rsb.QualityOfServiceSpec.Reliability.UNRELIABLE and qos.getOrdering() == rsb.QualityOfServiceSpec.Ordering.UNORDERED:
            self.__msgType = spread.UNRELIABLE_MESS
            self.__logger.debug("Chosen service type is UNRELIABLE_MESS,  value = %s", self.__msgType)
        elif qos.getReliability() == rsb.QualityOfServiceSpec.Reliability.UNRELIABLE and qos.getOrdering() == rsb.QualityOfServiceSpec.Ordering.ORDERED:
            self.__msgType = spread.FIFO_MESS
            self.__logger.debug("Chosen service type is FIFO_MESS,  value = %s", self.__msgType)
        elif qos.getReliability() == rsb.QualityOfServiceSpec.Reliability.RELIABLE and qos.getOrdering() == rsb.QualityOfServiceSpec.Ordering.UNORDERED:
            self.__msgType = spread.RELIABLE_MESS
            self.__logger.debug("Chosen service type is RELIABLE_MESS,  value = %s", self.__msgType)
        elif qos.getReliability() == rsb.QualityOfServiceSpec.Reliability.RELIABLE and qos.getOrdering() == rsb.QualityOfServiceSpec.Ordering.ORDERED:
            self.__msgType = spread.FIFO_MESS
            self.__logger.debug("Chosen service type is FIFO_MESS,  value = %s", self.__msgType)
        else:
            assert(False)

class InConnector(Connector,
                  rsb.transport.InConnector):
    def __init__(self, **kwargs):
        self.__logger = rsb.util.getLoggerByClass(self.__class__)

        self.__receiveThread = None
        self.__receiveTask = None
        self.__observerAction = None

        self.__scope = None

        super(InConnector, self).__init__(**kwargs)

    def setScope(self, scope):
        self.__logger.debug("Got new scope %s", scope)
        self.__scope = scope

    def activate(self):
        super(InConnector, self).activate()

        assert self.__scope is not None
        self.connection.join(self._groupName(self.__scope))

        self.__receiveTask = SpreadReceiverTask(self.connection,
                                                self.__observerAction,
                                                self.converterMap)
        self.__receiveThread = threading.Thread(target=self.__receiveTask)
        self.__receiveThread.setDaemon(True)
        self.__receiveThread.start()

    def deactivate(self):
        self.__receiveTask.interrupt()
        self.__receiveThread.join(timeout=1)
        self.__receiveThread = None
        self.__receiveTask = None

        super(InConnector, self).deactivate()

    def filterNotify(self, filter, action):
        self.__logger.debug("Ignoring filter %s with action %s", filter, action)

    def setObserverAction(self, observerAction):
        self.__observerAction = observerAction
        if self.__receiveTask != None:
            self.__logger.debug("Passing observer to receive task")
            self.__receiveTask.setObserverAction(observerAction)
        else:
            self.__logger.warn("Ignoring observer action %s because there is no dispatch task", observerAction)

rsb.transport.addConnector(InConnector)

class OutConnector(Connector,
                   rsb.transport.OutConnector):
    def __init__(self, **kwargs):
        self.__logger = rsb.util.getLoggerByClass(self.__class__)

        super(OutConnector, self).__init__(**kwargs)

    def handle(self, event):
        self.__logger.debug("Sending event: %s", event)

        if self.connection is None:
            self.__logger.warning("Connector not activated")
            return

        # Create one or more notification fragments for the event
        event.getMetaData().setSendTime()
        converter = self.getConverterForDataType(event.type)
        fragments = conversion.eventToNotifications(event, converter, self.MAX_MSG_LENGTH)

        # Send fragments
        self.__logger.debug("Sending %u fragments", len(fragments))
        for (i, fragment) in enumerate(fragments):
            serialized = fragment.SerializeToString()
            self.__logger.debug("Sending fragment %u of length %u", i + 1, len(serialized))

            # TODO respect QoS
            scopes     = event.scope.superScopes(True)
            groupNames = map(self._groupName, scopes)
            self.__logger.debug("Sending to scopes %s which are groupNames %s", scopes, groupNames)

            sent = self.connection.multigroup_multicast(self._msgType, tuple(groupNames), serialized)
            if (sent > 0):
                self.__logger.debug("Message sent successfully (bytes = %i)", sent)
            else:
                # TODO(jmoringe): propagate error
                self.__logger.warning("Error sending message, status code = %s", sent)

rsb.transport.addConnector(OutConnector)
