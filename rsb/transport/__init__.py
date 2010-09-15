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
import converter

from Queue import Queue, Empty
from rsb import EventProcessor
from rsb.util import getLoggerByClass
from threading import RLock

class Router(object):
    """
    Routers to publish and subscribe on events.
    
    @author: jwienke
    """

    def __init__(self, inPort=None, outPort=None, eventProcessor=EventProcessor()):
        """
        Creates a new router.
        
        @param inPort: port for ingoing communication or None for no port
        @param outPort: port for outgoing communication or None for no port
        @param eventProcessor: event processor to use
        """

        self.__logger = getLoggerByClass(self.__class__)

        if inPort:
            self.__inPort = inPort
            self.__eventProcessor = eventProcessor
            self.__inPort.setObserverAction(self.__eventProcessor.process)
        else:
            self.__inPort = None
            self.__eventProcessor = None
        if outPort:
            self.__outPort = outPort
        else:
            self.__outPort = None

        self.__active = False

    def __del__(self):
        if self.__active:
            self.deactivate()

    def activate(self):
        if not self.__active:
            self.__logger.info("Activating router")
            if self.__inPort:
                self.__inPort.activate()
            if self.__outPort:
                self.__outPort.activate()
            self.__active = True
        else:
            self.__logger.warning("Router was already activated")

    def deactivate(self):
        if self.__active:
            self.__logger.info("Deactivating router")
            if self.__inPort:
                self.__inPort.deactivate()
                self.__inPort.setObserverAction(None)
                self.__eventProcessor.deactivate()
            if self.__outPort:
                self.__outPort.deactivate()
            self.__active = False
        else:
            self.__logger.warning("Router was not active")

    def publish(self, event):
        if self.__active and self.__outPort:
            self.__logger.debug("Publishing event: %s" % event)
            self.__outPort.push(event)
        else:
            self.__logger.warning("Router is not active or has no outgoing port. Cannot publish.")

    def __notifyPorts(self, subscription, filterAction):
        if self.__inPort:
            for f in subscription.getFilters():
                self.__inPort.filterNotify(f, filterAction)

    def subscribe(self, subscription):
        self.__logger.debug("New subscription %s" % subscription)
        self.__notifyPorts(subscription, rsb.filter.FilterAction.ADD)
        if self.__eventProcessor:
            self.__eventProcessor.subscribe(subscription)

    def unsubscribe(self, subscription):
        self.__logger.debug("Remove subscription %s" % subscription)
        self.__notifyPorts(subscription, rsb.filter.FilterAction.REMOVE)
        if self.__eventProcessor:
            self.__eventProcessor.unsubscribe(subscription)

class QueueAndDispatchTask(object):
    """
    A task that receives events from an external thread and dispatches them to
    a registered observer.
    
    @author: jwienke
    """

    def __init__(self, observer=None):
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
                if self.__observer != None:
                    self.__observer(item)

            except Empty:
                continue

    def interrupt(self):
        self.__interruptionLock.acquire()
        self.__interrupted = True
        self.__interruptionLock.release()

    def dispatch(self, item):
        self.__queue.put(item)

    def setObserverAction(self, observer):
        """
        Sets the observer to execute with new elements to dispatch.
        
        @param observer: callable object with one argument, the item from the
                         queue. None for no action
        @todo: does this need locking?
        """
        self.__observer = observer


class Port(object):
    """
    Interface for transport-specific ports.
    
    @author: jwienke
    """

    def __init__(self, targetType, converterMap=None):
        """
        Creates a new port with a serialization type targetType.
        
        @param targetType: the serialization python type used
        @param converterMap: map of converters to use. If None, the global
                             map of converters for the selected targetType is
                             used
        """
        
        self.__logger = getLoggerByClass(self.__class__)
        
        if targetType == None:
            raise ValueError("Target type must be a class or primitive type, None given")
        
        if converterMap == None:
            self.__logger.debug("Using global converter map for target type %s" % targetType)
            self.__converterMap = converter.getGlobalConverterMap(targetType)
        else:
            self.__logger.debug("Using specified converter map for target type %s" % targetType)
            self.__converterMap = converterMap
        assert(self.__converterMap.getTargetType() == targetType)
        self.__targetType = targetType

    def getTargetType(self):
        """
        Returns the serialization type used for this port.
        
        @return: python serialization type
        """
        return self.__targetType

    def _getConverter(self, sourceType):
        """
        Returns the converter for the source type.
        
        @param sourceType: source type
        @return: converter
        @raise KeyError: no converter for the source type available
        """
        self.__logger.debug("Searching for converter with sourceType '%s' in map %s" % (sourceType, self.__converterMap))
        return self.__converterMap.getConverter(sourceType)
    
    def _getConverterMap(self):
        return self.__converterMap

    def activate(self):
        raise NotImplementedError()
    def deactivate(self):
        raise NotImplementedError()
    def publish(self, event):
        raise NotImplementedError()
    def filterNotify(self, filter, action):
        raise NotImplementedError()

    def setObserverAction(self, observerAction):
        """
        Sets the action used by the port to notify about incomming events.
        The call to this method must be thread-safe.
        
        @param observerAction: action called if a new message is received from
                               the port. Must accept an RSBEvent as parameter.
        """
        pass
