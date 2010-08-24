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

import logging

import rsb.filter
from Queue import Queue, Empty
from multiprocessing.synchronize import RLock

class Router(object):
    """
    Routers to publish and subscribe on events.
    
    @author: jwienke
    """

    def __init__(self, inPort, outPort):
        """
        Creates a new router.
        
        @param inPort: port for ingoing communication
        @param outPort: port for outgoing communication
        """
        
        self.__logger = logging.getLogger(str(self.__class__))
        self.__inPort = inPort
        self.__outPort = outPort
        self.__active = False
        
    def __del__(self):
        if self.__active:
            self.deactivate()

    def activate(self):
        if not self.__active:
            self.__logger.info("Activating router")
            self.__inPort.activate()
            self.__outPort.activate()
            self.__active = True
        else:
            self.__logger.warning("Router was already activated")
    
    def deactivate(self):
        if self.__active:
            self.__logger.info("Deactivating router")
            self.__inPort.deactivate()
            self.__outPort.deactivate()
            self.__active = False
        else:
            self.__logger.warning("Router was not active")
    
    def publish(self, event):
        if self.__active:
            self.__logger.debug("Publishing event: %s" % event)
            self.__outPort.push(event)
        else:
            self.__logger.warning("Router is not active. Cannot publish.")

    def __notifyPorts(self, subscription, filterAction):
        for f in subscription.getFilters():
            self.__inPort.filterNotify(f, filterAction)

    def subscribe(self, subscription):
        self.__notifyPorts(subscription, rsb.filter.FilterAction.ADD)
    
    def unsubscribe(self, subscription):
        self.__notifyPorts(subscription, rsb.filter.FilterAction.REMOVE)
        
class QueueAndDispatchTask(object):
    """
    A task that receives events from an external thread and dispatches them to
    a registered observer.
    
    @author: jwienke
    """
    
    def __init__(self, observer):
        """
        Constructs a new task object.
        
        @type observer: callable object with one argument, the item from the
                        queue
        @param observer: observer that will be called for every new item in the
                         queue
        """
        
        self.__queue = Queue()
        self.__interrupted = False
        self.__interruptionLock = RLock()
        self.__observer = observer
        
    def __call__(self):
        
        while True:
            
            # check interruption
            self.__interruptionLock.acquire()
            interrupted = self.__interrupted
            self.__interruptionLock.release()
            
            if interrupted:
                break
            
            try:
                
                item = self.__queue.get(True, 1)
                self.__observer(item)
                
            except Empty:
                continue
        
    def interrupt(self):
        self.__interruptionLock.acquire()
        self.__interrupted = True
        self.__interruptionLock.release()
        
    def dispatch(self, item):
        self.__queue.put(item)
        

class Port(object):
    """
    Interface for transport-specific p;orts.
    
    @author: jwienke
    """
    
    def activate(self):
        pass
    def deactivate(self):
        pass
    def publish(self, event):
        pass
    def filterNotify(self, filter, action):
        pass
    
    def setObserverAction(self, observerAction):
        """
        Sets the action used by the port to notify about incomming events.
        The call to this method must be thread-safe.
        
        @param observerAction: action called if a new message is received from
                               the port. Must accept an RSBEvent as parameter.
        """
        pass
