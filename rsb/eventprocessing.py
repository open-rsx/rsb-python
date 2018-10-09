# ============================================================
#
# Copyright (C) 2011 by Johannes Wienke
# Copyright (C) 2011-2018 Jan Moringen
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
# ============================================================

"""
Contains code mediating between the user interface and the transport layer.

.. codeauthor:: jwienke
.. codeauthor:: jmoringe
"""

import abc
import copy
import queue
import threading

import rsb.filter
import rsb.util


class ScopeDispatcher:
    """
    Maintains a map of :ref:`Scopes <scope>` to sink objects.

    .. codeauthor:: jmoringe
    """

    def __init__(self):
        self.__map = {}

    def __len__(self):
        return len(self.__map)

    def __bool__(self):
        return bool(self.__map)

    def add_sink(self, scope, sink):
        """
        Associate `sink` to `scope`.

        Args:
            scope (Scope):
                The scope to which `sink` should be associated.
            sink (object):
                The arbitrary object that should be associated to `scope`.
        """
        if scope in self.__map:
            sinks = self.__map[scope]
        else:
            sinks = []
            self.__map[scope] = sinks

        sinks.append(sink)

    def remove_sink(self, scope, sink):
        """
        Disassociate `sink` from `scope`.

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

    @property
    def sinks(self):
        """
        Return a generator yielding all sinks.

        Yields:
            sinks:
                A generator yielding all known sinks in an unspecified
                order.
        """
        for sinks in list(self.__map.values()):
            for sink in sinks:
                yield sink

    def matching_sinks(self, scope):
        """
        Return a generator yielding sinks matching `scope`.

        A sink matches `scope` if it was previously associated to
        `scope` or one of its super-scopes.

        Yields:
            sinks:
                A generator yielding all matching sinks in an
                unspecified order.
        """
        for sink in self.__map.get(scope, []):
            yield sink
        for scope in scope.super_scopes():
            for sink in self.__map.get(scope, []):
                yield sink


class BroadcastProcessor:
    """
    Implements synchronous broadcast dispatch to a list of handlers.

    .. codeauthor:: jmoringe
    """

    def __init__(self, handlers=None):
        self.__logger = rsb.util.get_logger_by_class(self.__class__)

        if handlers is None:
            self.__handlers = []
        else:
            self.__handlers = list(handlers)

    @property
    def handlers(self):
        return self.__handlers

    def add_handler(self, handler):
        self.__handlers.append(handler)

    def remove_handler(self, handler):
        self.__handlers.remove(handler)

    def __call__(self, event):
        self.handle(event)

    def handle(self, event):
        self.dispatch(event)

    def dispatch(self, event):
        for handler in self.handlers:
            handler(event)

    def __str__(self):
        return '<{} {} handlers at 0x{:x}>'.format(type(self).__name__,
                                                   len(self.handlers),
                                                   id(self))


class EventReceivingStrategy(metaclass=abc.ABCMeta):
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
    def add_handler(self, handler, wait):
        pass

    @abc.abstractmethod
    def remove_handler(self, handler, wait):
        pass

    @abc.abstractmethod
    def add_filter(self, the_filter):
        pass

    @abc.abstractmethod
    def remove_filter(self, the_filter):
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
    def set_connectors(self, connectors):
        pass

    @abc.abstractmethod
    def raise_event(self, block):
        """
        Receive the next event.

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

    def set_connectors(self, connectors):
        if not connectors:
            raise ValueError("There must be at least on connector")
        self.__connectors = connectors

    def raise_event(self, block):
        assert self.__connectors

        event = self.__connectors[0].raise_event(block)
        if event:
            event.meta_data.set_deliver_time()
        return event


class ParallelEventReceivingStrategy(PushEventReceivingStrategy):
    """
    Dispatches events to multiple handlers in parallel.

    An :obj:`PushEventReceivingStrategy` that dispatches events to multiple
    handlers in individual threads in parallel. Each handler is called only
    sequentially but potentially from different threads.

    .. codeauthor:: jwienke
    """

    def __init__(self, num_threads=5):
        self.__logger = rsb.util.get_logger_by_class(self.__class__)
        self.__pool = rsb.util.OrderedQueueDispatcherPool(
            thread_pool_size=num_threads, del_func=self.__deliver,
            filter_func=self.__filter)
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
            filter_copy = list(self.__filters)

        for flt in filter_copy:
            if not flt.match(event):
                return False
        return True

    def handle(self, event):
        """
        Dispatch the event to all registered listeners.

        Args:
            event:
                event to dispatch
        """
        self.__logger.debug("Processing event %s", event)
        event.meta_data.set_deliver_time()
        self.__pool.push(event)

    def add_handler(self, handler, wait):
        # We can ignore wait since the pool implements the desired
        # behavior.
        self.__pool.register_receiver(handler)

    def remove_handler(self, handler, wait):
        # We can ignore wait since the pool implements the desired
        # behavior.
        self.__pool.unregister_receiver(handler)

    def add_filter(self, the_filter):
        with self.__filtersMutex:
            self.__filters.append(the_filter)

    def remove_filter(self, the_filter):
        with self.__filtersMutex:
            self.__filters = [f for f in self.__filters if f != the_filter]


class FullyParallelEventReceivingStrategy(PushEventReceivingStrategy):
    """
    Dispatches events to multiple handlers that can be called in parallel.

    An :obj:`PushEventReceivingStrategy` that dispatches events to multiple
    handlers in individual threads in parallel. Each handler can be called
    in parallel for different requests.

    .. codeauthor:: jwienke
    """

    def __init__(self):
        self.__logger = rsb.util.get_logger_by_class(self.__class__)
        self.__filters = []
        self.__mutex = threading.RLock()
        self.__handlers = []

    def deactivate(self):
        pass

    class Worker(threading.Thread):

        def __init__(self, handler, event, filters):
            super().__init__(name='DispatcherThread')
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
        Dispatch the event to all registered listeners.

        Args:
            event:
                event to dispatch
        """
        self.__logger.debug("Processing event %s", event)
        event.meta_data.set_deliver_time()
        workers = []
        with self.__mutex:
            for h in self.__handlers:
                workers.append(self.Worker(h, event, list(self.__filters)))
        for w in workers:
            w.start()

    def add_handler(self, handler, wait):
        # We can ignore wait since the pool implements the desired
        # behavior.
        with self.__mutex:
            self.__handlers.append(handler)

    def remove_handler(self, handler, wait):
        # TODO anything required to implement wait functionality?
        with self.__mutex:
            self.__handlers.remove(handler)

    def add_filter(self, f):
        with self.__mutex:
            self.__filters.append(f)

    def remove_filter(self, the_filter):
        with self.__mutex:
            self.__filters = [f for f in self.__filters if f != the_filter]


class NonQueuingParallelEventReceivingStrategy(PushEventReceivingStrategy):
    """
    Dispatches events to handlers using a single thread and no queues.

    An :obj:`PushEventReceivingStrategy` that dispatches events to multiple
    handlers using a single thread and without queuing. Only a single buffer
    is used to decouple the transport from the registered handlers. In case
    the handler processing is slower than the transport, the transport will
    block on inserting events into this strategy. Callers must ensure that they
    are in no active call for #handle when deactivating this instance.

    .. codeauthor:: jwienke
    """

    def __init__(self):
        self.__logger = rsb.util.get_logger_by_class(self.__class__)
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
        event.meta_data.set_deliver_time()
        self.__queue.put(event, True)

    def add_handler(self, handler, wait):
        with self.__mutex:
            self.__handlers.append(handler)

    def remove_handler(self, handler, wait):
        with self.__mutex:
            self.__handlers.remove(handler)

    def add_filter(self, f):
        with self.__mutex:
            self.__filters.append(f)

    def remove_filter(self, the_filter):
        with self.__mutex:
            self.__filters = [f for f in self.__filters if f != the_filter]


class EventSendingStrategy(metaclass=abc.ABCMeta):

    @property
    @abc.abstractmethod
    def connectors(self):
        pass

    @abc.abstractmethod
    def add_connector(self, connector):
        pass

    @abc.abstractmethod
    def remove_connector(self, connector):
        pass

    @abc.abstractmethod
    def handle(self, event):
        pass


class DirectEventSendingStrategy(EventSendingStrategy):

    def __init__(self):
        self.__connectors = []

    @property
    def connectors(self):
        return self.__connectors

    def add_connector(self, connector):
        self.__connectors.append(connector)

    def remove_connector(self, connector):
        self.__connectors.remove(connector)

    def handle(self, event):
        for connector in self.__connectors:
            connector.handle(event)


class Configurator:
    """
    Superclass for in- and out-direction Configurator classes.

    Manages the basic aspects like the connector list and (de)activation that
    are not direction-specific.

    .. codeauthor:: jwienke
    .. codeauthor:: jmoringe
    """

    def __init__(self, connectors=None):
        self.__logger = rsb.util.get_logger_by_class(self.__class__)

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

    @property
    def scope(self):
        return self.__scope

    @scope.setter
    def scope(self, scope):
        """
        Define the scope the in route has to be set up.

        This will be called before calling #activate.

        Args:
            scope (rsb.Scope):
                the scope of the in route
        """
        self.__scope = scope
        self.__logger.debug("Got new scope %s", scope)
        for connector in self.connectors:
            connector.scope = scope

    @property
    def connectors(self):
        return self.__connectors

    @property
    def transport_urls(self):
        """
        Return the transport URLs of all used connectors.

        Returns:
            list:
                List of transport URLs.
        """
        return {x.get_transport_url() for x in self.__connectors}

    @property
    def active(self):
        return self.__active

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

    def set_quality_of_service_spec(self, qos):
        for connector in self.connectors:
            connector.quality_of_service_spec = qos


class InPushRouteConfigurator(Configurator):
    """
    Manages event receiving using a push strategy.

    Instances of this class manage the receiving, filtering and
    dispatching of events via one or more :obj:`rsb.transport.Connector` s
    and an :obj:`PushEventReceivingStrategy`.

    .. codeauthor:: jwienke
    .. codeauthor:: jmoringe
    """

    def __init__(self, connectors=None, receiving_strategy=None):
        """
        Create a new configurator.

        Args:
            connectors:
                Connectors through which events are received.
            receiving_strategy:
                The event receiving strategy according to which the filtering
                and dispatching of incoming events should be performed.
        """
        super().__init__(connectors)

        self.__logger = rsb.util.get_logger_by_class(self.__class__)

        if receiving_strategy is None:
            self.__receiving_strategy = ParallelEventReceivingStrategy()
        else:
            self.__receiving_strategy = receiving_strategy

        for connector in self.connectors:
            connector.set_observer_action(self.__receiving_strategy.handle)

    def deactivate(self):
        super().deactivate()

        for connector in self.connectors:
            connector.set_observer_action(None)
        self.__receiving_strategy.deactivate()

    def handler_added(self, handler, wait):
        self.__receiving_strategy.add_handler(handler, wait)

    def handler_removed(self, handler, wait):
        self.__receiving_strategy.remove_handler(handler, wait)

    def filter_added(self, the_filter):
        self.__receiving_strategy.add_filter(the_filter)
        for connector in self.connectors:
            connector.filter_notify(the_filter, rsb.filter.FilterAction.ADD)

    def filter_removed(self, the_filter):
        self.__receiving_strategy.remove_filter(the_filter)
        for connector in self.connectors:
            connector.filter_notify(the_filter, rsb.filter.FilterAction.REMOVE)


class InPullRouteConfigurator(Configurator):
    """
    Manages pull-based event receiving.

    Instances of this class manage the pull-based receiving of events via one
    or more :obj:`rsb.transport.Connector` s and an
    :obj:`PullEventReceivingStrategy`.

    .. codeauthor:: jwienke
    """

    def __init__(self, connectors=None, receiving_strategy=None):
        """
        Create a new configurator.

        Args:
            connectors:
                Connectors through which events are received.
            receiving_strategy:
                The event receiving strategy according to which the dispatching
                of incoming events should be performed.
        """
        super().__init__(connectors)

        self.__logger = rsb.util.get_logger_by_class(self.__class__)

        if receiving_strategy is None:
            self.__receiving_strategy = \
                FirstConnectorPullEventReceivingStrategy()
        else:
            self.__receiving_strategy = receiving_strategy
        self.__receiving_strategy.set_connectors(connectors)

    def get_receiving_strategy(self):
        return self.__receiving_strategy


class OutRouteConfigurator(Configurator):
    """
    Manages send events using one or more connectors and a sending strategy.

    Instances of this class manage the sending of events via one or
    more :obj:`rsb.transport.Connector` s and an :obj:`EventSendingStrategy`.

    .. codeauthor:: jmoringe
    """

    def __init__(self, connectors=None, sending_strategy=None):
        self.__logger = rsb.util.get_logger_by_class(self.__class__)

        super().__init__(connectors)

        if sending_strategy is None:
            self.__sending_strategy = DirectEventSendingStrategy()
        else:
            self.__sending_strategy = sending_strategy

        if connectors is not None:
            list(map(self.__sending_strategy.add_connector, connectors))

    def handle(self, event):
        if not self.active:
            raise RuntimeError("Trying to publish event on Configurator "
                               "which is not active.")

        self.__logger.debug("Publishing event: %s", event)
        self.__sending_strategy.handle(event)
