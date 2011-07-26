# ============================================================
#
# Copyright (C) 2010 by Johannes Wienke <jwienke at techfak dot uni-bielefeld dot de>
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

import threading
import uuid

import spread

import rsb.filter
import rsb.transport
from Protocol_pb2 import Notification, MetaData
from google.protobuf.message import DecodeError
from rsb.util import getLoggerByClass, unixMicrosecondsToTime
from rsb import Event, Scope, QualityOfServiceSpec
from rsb.transport.converter import UnknownConverterError
import hashlib
import math
import logging
import time
from rsb.rsbspread.Protocol_pb2 import UserInfo, UserTime
from multiprocessing import RLock

def makeKey(notification):
    key = notification.sender_id + '%08x' % notification.sequence_number
    return key

class Assembly(object):
    """
    A class that maintains a collection of fragments of one fragmented
    notification and assembles them if all fragments are received.

    @author: jwienke
    """

    def __init__(self, notification):
        self.__requiredParts = notification.num_data_parts
        assert(self.__requiredParts > 1)
        self.__id = makeKey(notification)
        self.__parts = {notification.data_part : notification}

    def add(self, notification):
        key = makeKey(notification)
        assert(key == self.__id)
        if notification.data_part in self.__parts:
            raise ValueError("Received part %u for notification with id %s again." % (notification.data_part, key))

        self.__parts[notification.data_part] = notification

        if len(self.__parts) == self.__requiredParts:
            return self.__join()
        else:
            return None

    def __join(self):
        keys = self.__parts.keys()
        keys.sort()
        finalData = ""
        for key in keys:
            finalData += self.__parts[key].data
        return bytearray(finalData)

class AssemblyPool(object):
    """
    Maintains the parallel joining of notfications that are received in an
    interleaved fashion.

    @author: jwienke
    """

    def __init__(self):
        self.__assemblies = {}

    def add(self, notification):
        if notification.num_data_parts == 1:
            return notification.data
        key = makeKey(notification)
        if not key in self.__assemblies:
            self.__assemblies[key] = Assembly(notification)
            return None
        else:
            result = self.__assemblies[key].add(notification)
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

        self.__logger = getLoggerByClass(self.__class__)

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
        self.__logger.debug("joined wakup group %s" % self.__wakeupGroup)

        while True:

            # check interruption
            self.__interruptionLock.acquire()
            interrupted = self.__interrupted
            self.__interruptionLock.release()

            if interrupted:
                break

            self.__logger.debug("waiting for new messages")
            message = self.__mailbox.receive()
            self.__logger.debug("received message %s" % message)
            try:

                # Process regular message
                if isinstance(message, spread.RegularMsgType):
                    # ignore the deactivate wakeup message
                    if self.__wakeupGroup in message.groups:
                        continue

                    notification = Notification()
                    notification.ParseFromString(message.message)
                    if self.__logger.isEnabledFor(logging.DEBUG):
                        data = str(notification)
                        if len(data) > 5000:
                            data = data[:5000] + " [... truncated for printing]"
                        self.__logger.debug("Received notification from bus: %s" % data)

                    joinedData = self.__assemblyPool.add(notification)

                    if joinedData:
                        # find a suitable converter
                        converter = self.__converterMap.getConverterForWireSchema(notification.wire_schema)
                        # build rsbevent from notification
                        event = Event()
                        event.sequenceNumber = notification.sequence_number
                        event.scope = Scope(notification.scope)
                        event.senderId = uuid.UUID(bytes=notification.sender_id)
                        event.type = converter.getDataType()
                        event.data = converter.deserialize(joinedData)

                        # meta data
                        event.metaData.createTime = unixMicrosecondsToTime(notification.meta_data.create_time)
                        event.metaData.sendTime = unixMicrosecondsToTime(notification.meta_data.send_time)
                        event.metaData.setReceiveTime()
                        for info in notification.meta_data.user_infos:
                            event.metaData.setUserInfo(info.key, info.value)
                        for time in notification.meta_data.user_times:
                            event.metaData.setUserTime(time.key, unixMicrosecondsToTime(time.timestamp))

                        self.__logger.debug("Sending event to dispatch task: %s" % event)

                        with self.__observerActionLock:
                            if self.__observerAction:
                                self.__observerAction(event)

                # Process membership message
                elif isinstance(message, spread.MembershipMsgType):
                    self.__logger.info("Received membership message for group `%s'" % message.group)

            except UnknownConverterError, e:
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

class SpreadPort(rsb.transport.Port):
    """
    Spread-based implementation of a port.

    @author: jwienke
    """

    __MAX_MSG_LENGTH = 100000

    def __init__(self, converterMap, options={}, spreadModule=spread):
        super(SpreadPort, self).__init__(bytearray, converterMap)
        host = options.get('host', None)
        port = options.get('port', '4803')
        if host:
            self.__daemonName = '%s@%s' % (port, host)
        else:
            self.__daemonName = port

        self.__spreadModule = spreadModule
        self.__logger = getLoggerByClass(self.__class__)
        self.__connection = None
        self.__groupNameSubscribers = {}
        """
        A map of scope subscriptions with the list of subscriptions.
        """
        self.__receiveThread = None
        self.__receiveTask = None
        self.__observerAction = None
        self.setQualityOfServiceSpec(QualityOfServiceSpec())

    def __del__(self):
        self.deactivate()

    def activate(self):
        if self.__connection == None:
            self.__logger.info("Activating spread port with daemon name %s" % self.__daemonName)

            self.__connection = self.__spreadModule.connect(self.__daemonName)

            self.__receiveTask = SpreadReceiverTask(self.__connection, self.__observerAction, self._getConverterMap())
            self.__receiveThread = threading.Thread(target=self.__receiveTask)
            self.__receiveThread.setDaemon(True)
            self.__receiveThread.start()

    def deactivate(self):
        if self.__connection != None:
            self.__logger.info("Deactivating spread port")

            self.__receiveTask.interrupt()
            self.__receiveThread.join(timeout=1)
            self.__receiveThread = None
            self.__receiveTask = None

            self.__connection.disconnect()
            self.__connection = None

            self.__logger.debug("SpreadPort deactivated")
        else:
            self.__logger.warning("spread port already deactivated")

    def __groupName(self, scope):
        sum = hashlib.md5()
        sum.update(scope.toString())
        return sum.hexdigest()[:-1]

    def push(self, event):

        self.__logger.debug("Sending event: %s" % event)

        if self.__connection == None:
            self.__logger.warning("Port not activated")
            return

        # convert data
        converter = self._getConverterForDataType(event.type)
        converted = converter.serialize(event.data)
        wireSchema = converter.getWireSchema()

        # find out the number of required messages
        if len(converted) > 0:
            requiredParts = int(math.ceil(float(len(converted)) / float(self.__MAX_MSG_LENGTH)))
        else:
            requiredParts = 1

        event.getMetaData().setSendTime()

        # build partial messages and send them
        self.__logger.debug("Sending %u messages" % requiredParts)
        for i in range(requiredParts):

            # create message
            n = Notification()
            n.sequence_number = event.sequenceNumber
            n.scope = event.scope.toString()
            n.sender_id = event.senderId.bytes
            n.wire_schema = wireSchema
            dataPart = converted[i * self.__MAX_MSG_LENGTH:i * self.__MAX_MSG_LENGTH + self.__MAX_MSG_LENGTH]
            n.data = str(dataPart)
            n.num_data_parts = requiredParts
            n.data_part = i
            # add meta-data
            md = n.meta_data
            md.create_time = rsb.util.timeToUnixMicroseconds(event.metaData.createTime)
            md.send_time = rsb.util.timeToUnixMicroseconds(event.metaData.sendTime)
            for (k, v) in event.metaData.userInfos.items():
                info = md.user_infos.add()
                info.key = k
                info.value = v
            for (k, v) in event.metaData.userTimes.items():
                time = md.user_times.add()
                time.key = k
                time.timestamp = rsb.util.timeToUnixMicroseconds(v)

            serialized = n.SerializeToString()

            self.__logger.debug("Sending part %u with data length %u" % (i + 1, len(dataPart)))

            # send message
            # TODO respect QoS
            scopes = event.scope.superScopes(True)
            groupNames = [self.__groupName(scope) for scope in scopes]
            self.__logger.debug("Sending to scopes %s which are groupNames %s" % (scopes, groupNames))
            sent = self.__connection.multigroup_multicast(self.__msgType, tuple(groupNames), serialized)
            if (sent > 0):
                self.__logger.debug("Message sent successfully (bytes = %i)" % sent)
            else:
                self.__logger.warning("Error sending message, status code = %s" % sent)

    def filterNotify(self, filter, action):

        self.__logger.debug("Got filter notification with filter %s and action %s" % (filter, action))

        if self.__connection == None:
            raise RuntimeError("SpreadPort not activated")

        # scope filter is the only interesting filter
        if (isinstance(filter, rsb.filter.ScopeFilter)):

            groupName = self.__groupName(filter.getScope());

            if action == rsb.filter.FilterAction.ADD:
                # join group if necessary, else only increment subscription counter

                if not groupName in self.__groupNameSubscribers:
                    self.__connection.join(groupName)
                    self.__groupNameSubscribers[groupName] = 1
                    self.__logger.info("joined group '%s'" % groupName)
                else:
                    self.__groupNameSubscribers[groupName] = self.__groupNameSubscribers[groupName] + 1

            elif action == rsb.filter.FilterAction.REMOVE:
                # leave group if no more subscriptions exist

                if not groupName in self.__groupNameSubscribers:
                    self.__logger.warning("Got unsubscribe for groupName '%s' even though I was not subscribed" % filter.getScope())
                    return

                assert(self.__groupNameSubscribers[groupName] > 0)
                self.__groupNameSubscribers[groupName] = self.__groupNameSubscribers[groupName] - 1
                if self.__groupNameSubscribers[groupName] == 0:
                    self.__connection.leave(groupName)
                    self.__logger.info("left group '%s'" % groupName)
                    del self.__groupNameSubscribers[groupName]

            else:
                self.__logger.warning("Received unknown filter action %s for filter %s" % (action, filter))

        else:
            self.__logger.debug("Ignoring filter %s with action %s" % (filter, action))

    def setQualityOfServiceSpec(self, qos):
        self.__logger.debug("Adapting service type for QoS %s" % qos)
        if qos.getReliability() == QualityOfServiceSpec.Reliability.UNRELIABLE and qos.getOrdering() == QualityOfServiceSpec.Ordering.UNORDERED:
            self.__msgType = spread.UNRELIABLE_MESS
            self.__logger.debug("Chosen service type is UNRELIABLE_MESS,  value = %s" % self.__msgType)
        elif qos.getReliability() == QualityOfServiceSpec.Reliability.UNRELIABLE and qos.getOrdering() == QualityOfServiceSpec.Ordering.ORDERED:
            self.__msgType = spread.FIFO_MESS
            self.__logger.debug("Chosen service type is FIFO_MESS,  value = %s" % self.__msgType)
        elif qos.getReliability() == QualityOfServiceSpec.Reliability.RELIABLE and qos.getOrdering() == QualityOfServiceSpec.Ordering.UNORDERED:
            self.__msgType = spread.RELIABLE_MESS
            self.__logger.debug("Chosen service type is RELIABLE_MESS,  value = %s" % self.__msgType)
        elif qos.getReliability() == QualityOfServiceSpec.Reliability.RELIABLE and qos.getOrdering() == QualityOfServiceSpec.Ordering.ORDERED:
            self.__msgType = spread.FIFO_MESS
            self.__logger.debug("Chosen service type is FIFO_MESS,  value = %s" % self.__msgType)
        else:
            assert(False)

    def setObserverAction(self, observerAction):
        self.__observerAction = observerAction
        if self.__receiveTask != None:
            self.__logger.debug("Passing observer to receive task")
            self.__receiveTask.setObserverAction(observerAction)
        else:
            self.__logger.warn("Ignoring observer action %s because there is no dispatch task" % observerAction)
