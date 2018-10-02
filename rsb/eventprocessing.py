# ============================================================
#
# Copyright (C) 2011 by Johannes Wienke <jwienke at techfak dot uni-bielefeld dot de>
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
A module with classes maintaining the processing of events between the
transport layer and the client interface.

.. codeauthor:: jwienke
.. codeauthor:: jmoringe
"""

import abc
import copy
import threading
import queue

import rsb.util
import rsb.filter


class ScopeDispatcher(object):
    """
    Maintains a map of :ref:`Scopes <scope>` to sink objects.

    .. codeauthor:: jmoringe
    """

    def __init__(self):
        self.__map = dict()

    def __len__(self):
        return len(self.__map)

    def __bool__(self):
        return bool(self.__map)

    def addSink(self, scope, sink):
        """
        Associates `sink` to `scope`.

        Args:
            scope (Scope):
                The scope to which `sink` should be associated.
            sink (object):
                The arbitrary object that should be associated to `scope`.
        """
        if scope in self.__map:
            sinks = self.__map[scope]
        else:
            sinks = list()
            self.__map[scope] = sinks

        sinks.append(sink)

    def removeSink(self, scope, sink):
        """
        Disassociates `sink` from `scope`.

        Args:
            scope (Scope):
                The scope from which `sink` should be disassociated.
            sink (object):
                The arbitrary object that should be disassociated from
                `scope`.
        """
        sinks = self.__map.get(scope)
        sinks.remove(sink)
        if not sinks:
            del self.__map[scope]

    def getSinks(self):
        """
        Returns a generator yielding all sinks.

        Yields:
            sinks:
                A generator yielding all known sinks in an unspecified
                order.
        """
        for sinks in list(self.__map.values()):
            for sink in sinks:
                yield sink

    sinks = property(getSinks)

    def matchingSinks(self, scope):
        """
        Returns a generator yielding sinks matching `scope`.

        A sink matches `scope` if it was previously associated to
        `scope` or one of its super-scopes.

        Yields:
            sinks:
                A generator yielding all matching sinks in an
                unspecified order.
        """
        for sink in self.__map.get(scope, []):
            yield sink
        for scope in scope.superScopes():
            for sink in self.__map.get(scope, []):
                yield sink


class BroadcastProcessor(object):
    """
    This event processor implements synchronous broadcast dispatch to
    a list of handlers.

    .. codeauthor:: jmoringe
    """

    def __init__(self, handlers=None):
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


class EventReceivingStrategy(object, metaclass=abc.ABCMeta):
    """
    Superclass for event receiving strategies.

    .. codeauthor:: jwienke
    """


class PushEventReceivingStrategy(EventReceivingStrategy):
    """
    Superclass for push-based event receiving strategies.

    .. codeauthor:: jmoringe
    .. codeauthor:: jwienke
    """

    @abc.abstractmethod
    def addHandler(self, handler, wait):
        pass

    @abc.abstractmethod
    def removeHandler(self, handler, wait):
        pass

    @abc.abstractmethod
    def addFilter(self, theFilter):
        pass

    @abc.abstractmethod
    def removeFilter(self, theFilter):
        pass

    @abc.abstractmethod
    def handle(self, event):
        pass


class PullEventReceivingStrategy(EventReceivingStrategy):
    """
    Superclass for pull-based event receiving.

    .. codeauthor:: jwienke
    """

    @abc.abstractmethod
    def setConnectors(self, connectors):
        pass

    @abc.abstractmethod
    def raiseEvent(self, block):
        """
        Receives the next event.

        Args:
            block (bool):
                if ``True``, wait for the next event. Else, immediately return,
                potentially a ``None``.
        """
        pass


class FirstConnectorPullEventReceivingStrategy(PullEventReceivingStrategy):
    """
    Directly receives events only from the first provided connector.

    .. codeauthor:: jwienke
    """

    def setConnectors(self, connectors):
        if not connectors:
            raise ValueError("There must be at least on connector")
        self.__connectors = connectors

    def raiseEvent(self, block):
        assert self.__connectors

        event = self.__connectors[0].raiseEvent(block)
        if event:
            event.metaData.setDeliverTime()
        return event


class ParallelEventReceivingStrategy(PushEventReceivingStrategy):
    """
    An :obj:`PushEventReceivingStrategy` that dispatches events to multiple
    handlers in individual threads in parallel. Each handler is called only
    sequentially but potentially from different threads.

    .. codeauthor:: jwienke
    """

    def __init__(self, numThreads=5):
        self.__logger = rsb.util.getLoggerByClass(self.__class__)
        self.__pool = rsb.util.OrderedQueueDispatcherPool(
            threadPoolSize=numThreads, delFunc=self.__deliver,
            filterFunc=self.__filter)
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
        # pylint: disable=no-self-use
        action(event)

    def __filter(self, action, event):
        with self.__filtersMutex:
            filterCopy = list(self.__filters)

        for flt in filterCopy:
            if not flt.match(event):
                return False
        return True

    def handle(self, event):
        """
        Dispatches the event to all registered listeners.

        Args:
            event:
                event to dispatch
        """
        self.__logger.debug("Processing event %s", event)
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

    def addFilter(self, theFilter):
        with self.__filtersMutex:
            self.__filters.append(theFilter)

    def removeFilter(self, theFilter):
        with self.__filtersMutex:
            self.__filters = [f for f in self.__filters if f != theFilter]


class FullyParallelEventReceivingStrategy(PushEventReceivingStrategy):
    """
    An :obj:`PushEventReceivingStrategy` that dispatches events to multiple
    handlers in individual threads in parallel. Each handler can be called
    in parallel for different requests.

    .. codeauthor:: jwienke
    """

    def __init__(self):
        self.__logger = rsb.util.getLoggerByClass(self.__class__)
        self.__filters = []
        self.__mutex = threading.RLock()
        self.__handlers = []

    def deactivate(self):
        pass

    class Worker(threading.Thread):

        def __init__(self, handler, event, filters):
            threading.Thread.__init__(self, name='DispatcherThread')
            self.handler = handler
            self.event = event
            self.filters = filters

        def run(self):

            for f in self.filters:
                if not f.match(self.event):
                    return

            self.handler(self.event)

    def handle(self, event):
        """
        Dispatches the event to all registered listeners.

        Args:
            event:
                event to dispatch
        """
        self.__logger.debug("Processing event %s", event)
        event.metaData.setDeliverTime()
        workers = []
        with self.__mutex:
            for h in self.__handlers:
                workers.append(self.Worker(h, event, list(self.__filters)))
        for w in workers:
            w.start()

    def addHandler(self, handler, wait):
        # We can ignore wait since the pool implements the desired
        # behavior.
        with self.__mutex:
            self.__handlers.append(handler)

    def removeHandler(self, handler, wait):
        # TODO anything required to implement wait functionality?
        with self.__mutex:
            self.__handlers.remove(handler)

    def addFilter(self, f):
        with self.__mutex:
            self.__filters.append(f)

    def removeFilter(self, theFilter):
        with self.__mutex:
            self.__filters = [f for f in self.__filters if f != theFilter]


class NonQueuingParallelEventReceivingStrategy(PushEventReceivingStrategy):
    """
    An :obj:`PushEventReceivingStrategy` that dispatches events to multiple
    handlers using a single thread and without queuing. Only a single buffer
    is used to decouple the transport from the registered handlers. In case
    the handler processing is slower than the transport, the transport will
    block on inserting events into this strategy. Callers must ensure that they
    are in no active call for #handle when deactivating this instance.

    .. codeauthor:: jwienke
    """

    def __init__(self):
        self.__logger = rsb.util.getLoggerByClass(self.__class__)
        self.__filters = []
        self.__mutex = threading.RLock()
        self.__handlers = []
        self.__queue = queue.Queue(1)
        self.__interrupted = False
        self.__thread = threading.Thread(target=self.__work)
        self.__thread.start()

    def deactivate(self):
        self.__interrupted = True
        self.__queue.put(None, True)
        self.__thread.join()

    def __work(self):

        while True:

            event = self.__queue.get(True)
            # interruption checking is handled here and not in the head of the
            # loop since we need put an artificial item into the queue when
            # deactivating this strategy and this item must never receive at
            # any handler
            if self.__interrupted:
                return

            with self.__mutex:
                for f in self.__filters:
                    if not f.match(event):
                        return
                for handler in self.__handlers:
                    handler(event)

    def handle(self, event):
        self.__logger.debug("Processing event %s", event)
        event.metaData.setDeliverTime()
        self.__queue.put(event, True)

    def addHandler(self, handler, wait):
        with self.__mutex:
            self.__handlers.append(handler)

    def removeHandler(self, handler, wait):
        with self.__mutex:
            self.__handlers.remove(handler)

    def addFilter(self, f):
        with self.__mutex:
            self.__filters.append(f)

    def removeFilter(self, theFilter):
        with self.__mutex:
            self.__filters = [f for f in self.__filters if f != theFilter]


class EventSendingStrategy(object):
    def getConnectors(self):
        raise NotImplementedError

    connectors = property(getConnectors)

    def addConnector(self, connector):
        raise NotImplementedError

    def removeConnector(self, connector):
        raise NotImplementedError

    def handle(self, event):
        raise NotImplementedError


class DirectEventSendingStrategy(EventSendingStrategy):
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


class Configurator(object):
    """
    Superclass for in- and out-direction Configurator classes. Manages
    the basic aspects like the connector list and (de)activation that
    are not direction-specific.

    .. codeauthor:: jwienke
    .. codeauthor:: jmoringe
    """

    def __init__(self, connectors=None):
        self.__logger = rsb.util.getLoggerByClass(self.__class__)

        self.__scope = None
        if connectors is None:
            self.__connectors = []
        else:
            self.__connectors = copy.copy(connectors)
        self.__active = False

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

        Args:
            scope (rsb.Scope):
                the scope of the in route
        """
        self.__scope = scope
        self.__logger.debug("Got new scope %s", scope)
        for connector in self.connectors:
            connector.setScope(scope)

    scope = property(getScope, setScope)

    def getConnectors(self):
        return self.__connectors

    connectors = property(getConnectors)

    def getTransportURLs(self):
        """
        Return list of transport URLs describing the connectors
        managed by the configurator.

        Returns:
            list:
                List of transport URLs.
        """
        return set(x.getTransportURL() for x in self.__connectors)

    transportURLs = property(getTransportURLs)

    def isActive(self):
        return self.__active

    active = property(isActive)

    def activate(self):
        if self.__active:
            raise RuntimeError("Configurator is already active")

        self.__logger.info("Activating configurator")
        for connector in self.connectors:
            connector.activate()

        self.__active = True

    def deactivate(self):
        if not self.__active:
            raise RuntimeError("Configurator is not active")

        self.__logger.info("Deactivating configurator")
        for connector in self.connectors:
            connector.deactivate()

        self.__active = False

    def setQualityOfServiceSpec(self, qos):
        for connector in self.connectors:
            connector.setQualityOfServiceSpec(qos)


class InPushRouteConfigurator(Configurator):
    """
    Instances of this class manage the receiving, filtering and
    dispatching of events via one or more :obj:`rsb.transport.Connector` s
    and an :obj:`PushEventReceivingStrategy`.

    .. codeauthor:: jwienke
    .. codeauthor:: jmoringe
    """

    def __init__(self, connectors=None, receivingStrategy=None):
        """
        Creates a new configurator which manages ``connectors`` and
        ``receivingStrategy``.

        Args:
            connectors:
                Connectors through which events are received.
            receivingStrategy:
                The event receiving strategy according to which the filtering
                and dispatching of incoming events should be performed.
        """
        super(InPushRouteConfigurator, self).__init__(connectors)

        self.__logger = rsb.util.getLoggerByClass(self.__class__)

        if receivingStrategy is None:
            self.__receivingStrategy = ParallelEventReceivingStrategy()
        else:
            self.__receivingStrategy = receivingStrategy

        for connector in self.connectors:
            connector.setObserverAction(self.__receivingStrategy.handle)

    def deactivate(self):
        super(InPushRouteConfigurator, self).deactivate()

        for connector in self.connectors:
            connector.setObserverAction(None)
        self.__receivingStrategy.deactivate()

    def handlerAdded(self, handler, wait):
        self.__receivingStrategy.addHandler(handler, wait)

    def handlerRemoved(self, handler, wait):
        self.__receivingStrategy.removeHandler(handler, wait)

    def filterAdded(self, theFilter):
        self.__receivingStrategy.addFilter(theFilter)
        for connector in self.connectors:
            connector.filterNotify(theFilter, rsb.filter.FilterAction.ADD)

    def filterRemoved(self, theFilter):
        self.__receivingStrategy.removeFilter(theFilter)
        for connector in self.connectors:
            connector.filterNotify(theFilter, rsb.filter.FilterAction.REMOVE)


class InPullRouteConfigurator(Configurator):
    """
    Instances of this class manage the pull-based receiving of events via one
    or more :obj:`rsb.transport.Connector` s and an
    :obj:`PullEventReceivingStrategy`.

    .. codeauthor:: jwienke
    """

    def __init__(self, connectors=None, receivingStrategy=None):
        """
        Creates a new configurator which manages ``connectors`` and
        ``receivingStrategy``.

        Args:
            connectors:
                Connectors through which events are received.
            receivingStrategy:
                The event receiving strategy according to which the dispatching
                of incoming events should be performed.
        """
        super(InPullRouteConfigurator, self).__init__(connectors)

        self.__logger = rsb.util.getLoggerByClass(self.__class__)

        if receivingStrategy is None:
            self.__receivingStrategy = FirstConnectorPullEventReceivingStrategy()
        else:
            self.__receivingStrategy = receivingStrategy
        self.__receivingStrategy.setConnectors(connectors)

    def getReceivingStrategy(self):
        return self.__receivingStrategy


class OutRouteConfigurator(Configurator):
    """
    Instances of this class manage the sending of events via one or
    more :obj:`rsb.transport.Connector` s and an :obj:`EventSendingStrategy`.

    .. codeauthor:: jmoringe
    """

    def __init__(self, connectors=None, sendingStrategy=None):
        self.__logger = rsb.util.getLoggerByClass(self.__class__)

        super(OutRouteConfigurator, self).__init__(connectors)

        if sendingStrategy is None:
            self.__sendingStrategy = DirectEventSendingStrategy()
        else:
            self.__sendingStrategy = sendingStrategy

        if connectors is not None:
            list(map(self.__sendingStrategy.addConnector, connectors))

    def handle(self, event):
        if not self.active:
            raise RuntimeError("Trying to publish event on Configurator "
                               "which is not active.")

        self.__logger.debug("Publishing event: %s", event)
        self.__sendingStrategy.handle(event)
