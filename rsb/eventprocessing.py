# ============================================================
#
# Copyright (C) 2011 by Johannes Wienke <jwienke at techfak dot uni-bielefeld dot de>
# Copyright (C) 2011 Jan Moringen <jmoringe@techfak.uni-bielefeld.de>
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

class BroadcastProcessor (object):
    """
    This event processor implements synchronous broadcast dispatch to
    a list of handlers.

    @author: jmoringe
    """
    def __init__(self, handlers = None):
        if handlers is None:
            self.__handlers = []
        else:
            self.__handlers = handlers

    def getHandlers(self):
        return self.__handlers

    def addHandler(self, handler):
        self.__handlers.append(handler)

    def removeHandler(self, handler):
        self.__handlers.remove(handler)

    handlers = property(getHandlers)

    def __call__(self, event):
        self.handle(event)

    def handle(self, event):
        self.dispatch(event)

    def dispatch(self, event):
        for handler in sefl.handlers:
            handler(event)

    def __str__(self):
        return '<%s %d handlers at 0x%x>' \
            % (type(self).__name__,
               len(self.handlers),
               id(self))

class EventReceivingStrategy(object):
    """
    Superclass for event receiving strategies.

    @author: jmoringe
    """
    def __init__(self):
        pass

    def addFilter(self, filter):
        raise NotImplementedError

    def removeFilter(self, filter):
        raise NotImplementedError

    def addHandler(self, handler):
        raise NotImplementedError

    def removeHandler(self, hanlder):
        raise NotImplementedError

    def handle(self):
        raise NotImplementedError


class ParallelEventReceivingStrategy(EventReceivingStrategy):
    """
    An L{EventReceivingStrategy} that dispatches events to multiple
    handlers in individual threads in parallel.

    @author: jwienke
    """

    def __init__(self, numThreads=5):
        self.__logger = getLoggerByClass(self.__class__)
        self.__pool = OrderedQueueDispatcherPool(threadPoolSize=numThreads, delFunc=self.__deliver, filterFunc=self.__filter)
        self.__pool.start()
        self.__filters = []
        self.__filtersMutex = RLock()

    def __del__(self):
        self.__logger.debug("Destructing ParallelEventReceivingStrategy")
        self.deactivate()

    def deactivate(self):
        self.__logger.debug("Deactivating ParallelEventReceivingStrategy")
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

    def handle(self, event):
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

class EventSendingStrategy (object):
    def handle(self, event):
        raise NotImplementedError

class Configurator (object):
    """
    Superclass for in- and out-direction Configurator classes. Manages
    the basic aspects like the connector list and (de)activation that
    are not direction-specific.

    @author: jwienke
    @author: jmoringe
    """
    def __init__(self, connectors = None):
        self.__logger = getLoggerByClass(self.__class__)

        if connectors is None:
            self.__connectors = []
        else:
            self.__connectors = connectors
        self.__active     = False

    def __del__(self):
        self.__logger.debug("Destructing Configurator")
        if self.__active:
            self.deactivate()

    def getConnectors(self):
        return self.__connectors

    connectors = property(getConnectors)

    def isActive(self):
        return self.__active

    active = property(isActive)

    def activate(self):
        if self.__active:
            raise RuntimeError, "Configurator is already active"

        self.__logger.info("Activating configurator")
        for connector in self.connectors:
            connector.activate()
        self.__active = True

    def deactivate(self):
        if not self.__active:
            raise RuntimeError, "Configurator is not active"

        self.__logger.info("Deactivating configurator")
        for connector in self.connectors:
            connector.deactivate()
        self.__active = False

    def setQualityOfServiceSpec(self, qos):
        for connector in self.connectors:
            connector.setQualityOfServiceSpec(qos)

class InRouteConfigurator(Configurator):
    """
    Instances of this class manage the receiving, filtering and
    dispatching of events via one or more L{rsb.transport.Connector} s
    and an L{EventReceivingStrategy}.

    @author: jwienke
    @author: jmoringe
    """

    def __init__(self, connectors = None, receivingStrategy = None):
        """
        Creates a new configurator which manages B{connectors} and
        B{receivingStrategy}.

        @param connectors: Connectors through which events are received.

        @param receivingStrategy: The event receiving strategy
                                  according to which the filtering and
                                  dispatching of incoming events
                                  should be performed.
        """
        super(InRouteConfigurator, self).__init__(connectors)

        self.__logger = getLoggerByClass(self.__class__)

        if receivingStrategy is None:
            self.__receivingStrategy = ParallelEventReceivingStrategy()
        else:
            self.__receivingStrategy = receivingStrategy

        for connector in self.connectors:
            connector.setObserverAction(self.__receivingStrategy.handle)

    def deactivate(self):
        super(InRouteConfigurator, self).deactivate()

        for connector in self.connectors:
            connector.setObserverAction(None)
        self.__receivingStrategy.deactivate()

    def handlerAdded(self, handler, wait):
        self.__receivingStrategy.addHandler(handler, wait)

    def handlerRemoved(self, handler, wait):
        self.__receivingStrategy.removeHandler(handler, wait)

    def filterAdded(self, filter):
        self.__receivingStrategy.addFilter(filter)
        for connector in self.connectors:
            connector.filterNotify(filter, FilterAction.ADD)

class OutRouteConfigurator(Configurator):
    """
    Instances of this class manage the sending of events via one or
    more L{rsb.transport.Connector} s and an L{EventSendingStrategy}.

    @author: jmoringe
    """

    def __init__(self, connectors = None, sendingStrategy = None):
        super(OutRouteConfigurator, self).__init__(connectors)

        self.__logger = getLoggerByClass(self.__class__)

    def publish(self, event):
        if not self.active:
            raise RuntimeError, "Trying to publish event on Configurator which is not active."

        self.__logger.debug("Publishing event: %s" % event)
        for connector in self.connectors:
            connector.push(event)
