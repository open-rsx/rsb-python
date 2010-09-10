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
import Notification_pb2
from rsb.transport import QueueAndDispatchTask, UnknownConverterError
from Notification_pb2 import Notification
from google.protobuf.message import DecodeError
from rsb.util import getLoggerByClass
from rsb import RSBEvent

class SpreadReceiverTask(object):
    """
    Thread used to receive messages from a spread connection.
    
    @author: jwienke
    """

    def __init__(self, mailbox, dispatchTask, converterMap):
        """
        Constructor.
        
        @param mailbox: spread mailbox to receive from
        @param dispatchTask: task that dispatches events
        @param converterMap: converters for data
        """

        self.__logger = getLoggerByClass(self.__class__)

        self.__interrupted = False
        self.__interruptionLock = threading.RLock()

        self.__mailbox = mailbox
        self.__dispatchTask = dispatchTask

        self.__converterMap = converterMap
        assert(converterMap.getTargetType() == str)

        self.__taskId = uuid.uuid1()
        # narf, spread groups are 32 chars long but 0-terminated... truncate id
        self.__wakeupGroup = str(self.__taskId).replace("-", "")[:-1]

    def __call__(self):

        # join my id to receive interrupt messages.
        # receive cannot have a timeout, hence we need a way to stop receiving
        # messages on interruption even if no one else sends messages.
        # Otherwise deactivate blocks until another message is received.
        self.__mailbox.join(self.__wakeupGroup)

        while True:

            # check interruption
            self.__interruptionLock.acquire()
            interrupted = self.__interrupted
            self.__interruptionLock.release()

            if interrupted:
                break

            message = self.__mailbox.receive()
            try:

                # ignore the deactivate wakeup message
                if self.__wakeupGroup in message.groups:
                    continue

                notification = Notification()
                notification.ParseFromString(message.message)

                # build rsbevent from notification
                event = RSBEvent()
                event.uri = notification.uri
                event.type = notification.type_id
                event.data = self.__converterMap.getConverter(event.type).deserialize(notification.data.binary)

                self.__dispatchTask.dispatch(event)

            except (AttributeError, TypeError), e:
                self.__logger.info("Attribute or TypeError receiving message: %s" % e)
            except UnknownConverterError, e:
                self.__logger.error("Unable to deserialize message> %s", e)
            except DecodeError, e:
                self.__logger.error("Error decoding notification: %s", e)

        # leave task id group to clean up
        self.__mailbox.leave(self.__wakeupGroup)

    def interrupt(self):
        self.__interruptionLock.acquire()
        self.__interrupted = True
        self.__interruptionLock.release()

        # send the interruption message to wake up receive as mentioned above
        self.__mailbox.multicast(spread.RELIABLE_MESS, self.__wakeupGroup, "")


class SpreadPort(rsb.transport.Port):
    """
    Spread-based implementation of a port.
    
    @author: jwienke 
    """

    def __init__(self, spreadModule=spread, converterMap=None):
        rsb.transport.Port.__init__(self, str, converterMap)
        self.__spreadModule = spreadModule
        self.__logger = getLoggerByClass(self.__class__)
        self.__connection = None
        self.__uriSubscribers = {}
        """
        A map of uri subscriptions with the list of subscriptions.
        """
        self.__receiveThread = None
        self.__receiveTask = None
        self.__dispatchThread = None
        self.__dispatchTask = None
        self.__observerAction = None

    def activate(self):
        if self.__connection == None:
            self.__logger.info("Activating spread port")

            self.__connection = self.__spreadModule.connect()

            self.__dispatchTask = QueueAndDispatchTask(self.__observerAction)
            self.__dispatchThread = threading.Thread(target=self.__dispatchTask)
            self.__dispatchThread.start()

            self.__receiveTask = SpreadReceiverTask(self.__connection, self.__dispatchTask, self._getConverterMap())
            self.__receiveThread = threading.Thread(target=self.__receiveTask)
            self.__receiveThread.start()

    def deactivate(self):
        if self.__connection != None:
            self.__logger.info("Deactivating spread port")

            self.__receiveTask.interrupt()
            self.__receiveThread.join()
            self.__receiveThread = None
            self.__receiveTask = None

            self.__dispatchTask.interrupt()
            self.__dispatchThread.join()
            self.__dispatchThread = None
            self.__dispatchTask = None

            self.__connection.disconnect()
            self.__connection = None
        else:
            self.__logger.warning("spread port already deactivated")

    def push(self, event):

        self.__logger.debug("Sending event: %s" % event)

        if self.__connection == None:
            self.__logger.warning("Port not activated")
            return

        # create message
        n = Notification_pb2.Notification()
        n.eid = "not set yet"
        n.uri = event.uri
        n.standalone = False
        n.type_id = event.type
        converted = self._getConverter(event.type).serialize(event.data)
        n.data.binary = converted
        n.data.length = len(converted)

        serialized = n.SerializeToString()

        # send message
        sent = self.__connection.multicast(spread.RELIABLE_MESS, event.uri, serialized)
        if (sent > 0):
            self.__logger.debug("Message sent successfully (bytes = %i)" % sent)
        else:
            self.__logger.warning("Error sending message, status code = %s" % sent)

    def filterNotify(self, filter, action):

        if self.__connection == None:
            raise RuntimeError("SpreadPort not activated")

        # scope filter is the only interesting filter
        if (isinstance(filter, rsb.filter.ScopeFilter)):

            uri = filter.getURI()

            if action == rsb.filter.FilterAction.ADD:
                # join group if necessary, else only increment subscription counter

                if not uri in self.__uriSubscribers:
                    self.__connection.join(uri)
                    self.__uriSubscribers[uri] = 1
                    self.__logger.info("joined group '%s'" % uri)
                else:
                    self.__uriSubscribers[uri] = self.__uriSubscribers[uri] + 1

            elif action == rsb.filter.FilterAction.REMOVE:
                # leave group if no more subscriptions exist

                if not uri in self.__uriSubscribers:
                    self.__logger.warning("Got unsubscribe for uri '%s' eventhough I was not subscribed" % filter.getURI())
                    return

                assert(self.__uriSubscribers[uri] > 0)
                self.__uriSubscribers[uri] = self.__uriSubscribers[uri] - 1
                if self.__uriSubscribers[uri] == 0:
                    self.__connection.leave(uri)
                    self.__logger.info("left group '%s'" % uri)
                    del self.__uriSubscribers[uri]

            else:
                self.__logger.warning("Received unknown filter action %s for filter %s" % (action, filter))

        else:
            self.__logger.debug("Ignoring filter %s with action %s" % (filter, action))

    def setObserverAction(self, observerAction):
        self.__observerAction = observerAction
        if self.__dispatchTask != None:
            self.__dispatchTask.setObserverAction(observerAction)
