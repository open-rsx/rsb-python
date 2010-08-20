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

"""
Spread port implementation for RSB.

@author: jwienke
"""

import logging

import spread

import rsb
import rsb.filter
import Notification_pb2

class SpreadReceiverTask:
    """
    Thread used to receive messages from a spread connection.
    
    @author: jwienke
    """
    
    def __init__(self, mailbox):
        """
        Constructor.
        
        @param mailbox: spread mailbox to receive from
        """
        
        self.__interrupted = False
        self.__interruptionLock = threading.RLock()
        
        self.__mailbox = mailbox
        
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
            # TODO is setting 
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
                
                print "got message: %s" % message.message
            except (AttributeError, TypeError): 
                # nothing to do here, this is not a regular message
                pass
            
        # leave task id group to clean up
        self.__mailbox.leave(self.__wakeupGroup)
                    
    def interrupt(self):
        self.__interruptionLock.acquire()
        self.__interrupted = True
        self.__interruptionLock.release()
        
        # send the interruption message to wake up receive as mentioned above
        self.__mailbox.multicast(spread.RELIABLE_MESS, self.__wakeupGroup, "")
        

class SpreadPort(rsb.Port):
    """
    Spread-based implementation of a port.
    
    @author: jwienke 
    """
    
    def __init__(self, spreadModule = spread):
        self.__spreadModule = spreadModule
        self.__logger = logging.getLogger(str(self.__class__))
        self.__connection = None
        self.__uriSubscribers = {}
        """
        A map of uri subscriptions with the list of subscriptions.
        """
        self.__receiveThread = None
        self.__receiveTask = None
        
    def activate(self):
        if self.__connection == None:
            self.__logger.info("Activating spread port")
            self.__connection = self.__spreadModule.connect()
            self.__receiveTask = SpreadReceiverTask(self.__connection)
            self.__receiveThread = threading.Thread(target = self.__receiveTask)
            self.__receiveThread.start()
        
    def deactivate(self):
        if self.__connection != None:
            self.__logger.info("Deactivating spread port")
            self.__receiveTask.interrupt()
            self.__receiveThread.join()
            self.__receiveThread = None
            self.__receiveTask = None
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
        pass