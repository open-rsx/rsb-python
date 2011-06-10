# ============================================================
#
# Copyright (C) 2011 by Johannes Wienke <jwienke at techfak dot uni-bielefeld dot de>
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

from rsb.util import getLoggerByClass, OrderedQueueDispatcherPool
import rsb
from threading import RLock
from rsb.filter import FilterAction

class EventProcessor(object):
    """
    @author: jwienke
    """

    def __init__(self, numThreads=5):
        self.__logger = getLoggerByClass(self.__class__)
        self.__pool = OrderedQueueDispatcherPool(threadPoolSize=numThreads, delFunc=self.__deliver, filterFunc=self.__filter)
        self.__pool.start()
        self.__filters = []
        self.__filtersMutex = RLock()

    def __del__(self):
        self.__logger.debug("Destructing EventProcesor")
        self.deactivate()

    def deactivate(self):
        self.__logger.debug("Deactivating EventProcesor")
        if self.__pool:
            self.__pool.stop()
            self.__pool = None

    def __deliver(self, action, event):
        action(event)

    def __filter(self, action, event):
        with self.__filtersMutex:
            filterCopy = list(self.__filters)

        for filter in filterCopy:
            if not filter.match(event):
                return False
        return True

    def process(self, event):
        """
        Dispatches the event to all registered listeners.

        @type event: Event
        @param event: event to dispatch
        """
        self.__logger.debug("Processing event %s" % event)
        event.metaData.setDeliverTime()
        self.__pool.push(event)

    def addHandler(self, handler, wait):
        # We can ignore wait since the pool implements the desired
        # behavior.
        self.__pool.registerReceiver(handler)

    def removeHandler(self, handler, wait):
        # We can ignore wait since the pool implements the desired
        # behavior.
        self.__pool.unregisterReceiver(handler)

    def addFilter(self, filter):
        with self.__filtersMutex:
            self.__filters.append(filter)

class Router(object):
    """
    Routers to publish and subscribe on events.

    @author: jwienke
    """

    def __init__(self, inPort=None, outPort=None, eventProcessor=None):
        """
        Creates a new router.

        @param inPort: port for ingoing communication or None for no port
        @param outPort: port for outgoing communication or None for no port
        @param eventProcessor: event processor to use
        """

        self.__logger = getLoggerByClass(self.__class__)

        self.__logger.debug("Creating router with inPort = %s, outPort = %s and eventProcessor = %s" % (inPort, outPort, eventProcessor))

        if inPort:
            self.__inPort = inPort
            self.__eventProcessor = eventProcessor
            if self.__eventProcessor == None:
                self.__eventProcessor = EventProcessor()
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
        self.__logger.debug("Destructing router")
        if self.__active:
            self.deactivate()

    def setQualityOfServiceSpec(self, qos):
        if self.__inPort:
            self.__inPort.setQualityOfServiceSpec(qos)
        if self.__outPort:
            self.__outPort.setQualityOfServiceSpec(qos)

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

    def handlerAdded(self, handler, wait):
        self.__eventProcessor.addHandler(handler, wait)

    def handlerRemoved(self, handler, wait):
        self.__eventProcessor.removeHandler(handler, wait)

    def filterAdded(self, filter):
        self.__eventProcessor.addFilter(filter)
        self.__inPort.filterNotify(filter, FilterAction.ADD)
