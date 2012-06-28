# ============================================================
#
# Copyright (C) 2011 by Johannes Wienke <jwienke at techfak dot uni-bielefeld dot de>
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
A module with classes maintaining the processing of events between the transport
layer and the client interface.

@author: jwienke
@author: jmoringe
"""

import copy
import threading

import rsb.util

import rsb
import rsb.filter

class BroadcastProcessor (object):
    """
    This event processor implements synchronous broadcast dispatch to
    a list of handlers.

    @author: jmoringe
    """
    def __init__(self, handlers = None):
        self.__logger = rsb.util.getLoggerByClass(self.__class__)

        if handlers is None:
            self.__handlers = []
        else:
            self.__handlers = list(handlers)

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
        for handler in self.handlers:
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
        self.__logger = rsb.util.getLoggerByClass(self.__class__)
        self.__pool = rsb.util.OrderedQueueDispatcherPool(threadPoolSize=numThreads, delFunc=self.__deliver, filterFunc=self.__filter)
        self.__pool.start()
        self.__filters = []
        self.__filtersMutex = threading.RLock()

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
    def getConnectors(self):
        raise NotImplementedError

    connectors = property(getConnectors)

    def addConnector(self, connector):
        raise NotImplementedError

    def removeConnector(self, connector):
        raise NotImplementedError

    def handle(self, event):
        raise NotImplementedError

class DirectEventSendingStrategy (EventSendingStrategy):
    def __init__(self):
        self.__connectors = []

    def getConnectors(self):
        return self.__connectors

    def addConnector(self, connector):
        self.__connectors.append(connector)

    def removeConnector(self, connector):
        self.__connectors.remove(connector)

    def handle(self, event):
        for connector in self.__connectors:
            connector.handle(event)

class Configurator (object):
    """
    Superclass for in- and out-direction Configurator classes. Manages
    the basic aspects like the connector list and (de)activation that
    are not direction-specific.

    @author: jwienke
    @author: jmoringe
    """
    def __init__(self, connectors = None):
        self.__logger = rsb.util.getLoggerByClass(self.__class__)

        self.__scope = None
        if connectors is None:
            self.__connectors = []
        else:
            self.__connectors = copy.copy(connectors)
        self.__active     = False

    def __del__(self):
        self.__logger.debug("Destructing Configurator")
        if self.__active:
            self.deactivate()

    def getScope(self):
        return self.__scope

    def setScope(self, scope):
        """
        Defines the scope the in route has to be set up. This will be called
        before calling #activate.

        @param scope: the scope of the in route
        @type scope: rsb.Scope
        """
        self.__scope = scope
        self.__logger.debug("Got new scope %s" % scope)
        for connector in self.connectors:
            connector.setScope(scope)

    scope = property(getScope, setScope)

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

        self.__logger = rsb.util.getLoggerByClass(self.__class__)

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
            connector.filterNotify(filter, rsb.filter.FilterAction.ADD)

class OutRouteConfigurator(Configurator):
    """
    Instances of this class manage the sending of events via one or
    more L{rsb.transport.Connector} s and an L{EventSendingStrategy}.

    @author: jmoringe
    """

    def __init__(self, connectors = None, sendingStrategy = None):
        self.__logger = rsb.util.getLoggerByClass(self.__class__)

        super(OutRouteConfigurator, self).__init__(connectors)

        if sendingStrategy is None:
            self.__sendingStrategy = DirectEventSendingStrategy()
        else:
            self.__sendingStrategy = sendingStrategy

        if not connectors is None:
            map(self.__sendingStrategy.addConnector, connectors)

    def handle(self, event):
        if not self.active:
            raise RuntimeError, "Trying to publish event on Configurator which is not active."

        self.__logger.debug("Publishing event: %s" % event)
        self.__sendingStrategy.handle(event)
