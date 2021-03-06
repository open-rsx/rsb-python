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
        self._map = {}

    def __len__(self):
        return len(self._map)

    def __bool__(self):
        return bool(self._map)

    def add_sink(self, scope, sink):
        """
        Associate `sink` to `scope`.

        Args:
            scope (Scope):
                The scope to which `sink` should be associated.
            sink (object):
                The arbitrary object that should be associated to `scope`.
        """
        if scope in self._map:
            sinks = self._map[scope]
        else:
            sinks = []
            self._map[scope] = sinks

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
        sinks = self._map.get(scope)
        sinks.remove(sink)
        if not sinks:
            del self._map[scope]

    @property
    def sinks(self):
        """
        Return a generator yielding all sinks.

        Yields:
            sinks:
                A generator yielding all known sinks in an unspecified
                order.
        """
        for sinks in list(self._map.values()):
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
        for sink in self._map.get(scope, []):
            yield sink
        for scope in scope.super_scopes():
            for sink in self._map.get(scope, []):
                yield sink


class BroadcastProcessor:
    """
    Implements synchronous broadcast dispatch to a list of handlers.

    .. codeauthor:: jmoringe
    """

    def __init__(self, handlers=None):
        self._logger = rsb.util.get_logger_by_class(self.__class__)

        if handlers is None:
            self._handlers = []
        else:
            self._handlers = list(handlers)

    @property
    def handlers(self):
        return self._handlers

    def add_handler(self, handler):
        self._handlers.append(handler)

    def remove_handler(self, handler):
        self._handlers.remove(handler)

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


class ParallelEventReceivingStrategy(EventReceivingStrategy):
    """
    Dispatches events to multiple handlers in parallel.

    An :obj:`EventReceivingStrategy` that dispatches events to multiple
    handlers in individual threads in parallel. Each handler is called only
    sequentially but potentially from different threads.

    .. codeauthor:: jwienke
    """

    def __init__(self, num_threads=5):
        self._logger = rsb.util.get_logger_by_class(self.__class__)
        self._pool = rsb.util.OrderedQueueDispatcherPool(
            thread_pool_size=num_threads, del_func=self._deliver,
            filter_func=self._filter)
        self._pool.start()
        self._filters = []
        self._filtersMutex = threading.RLock()

    def __del__(self):
        self._logger.debug("Destructing ParallelEventReceivingStrategy")
        self.deactivate()

    def deactivate(self):
        self._logger.debug("Deactivating ParallelEventReceivingStrategy")
        if self._pool:
            self._pool.stop()
            self._pool = None

    def _deliver(self, action, event):
        action(event)

    def _filter(self, action, event):
        with self._filtersMutex:
            filter_copy = list(self._filters)

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
        self._logger.debug("Processing event %s", event)
        event.meta_data.set_deliver_time()
        self._pool.push(event)

    def add_handler(self, handler, wait):
        # We can ignore wait since the pool implements the desired
        # behavior.
        self._pool.register_receiver(handler)

    def remove_handler(self, handler, wait):
        # We can ignore wait since the pool implements the desired
        # behavior.
        self._pool.unregister_receiver(handler)

    def add_filter(self, the_filter):
        with self._filtersMutex:
            self._filters.append(the_filter)

    def remove_filter(self, the_filter):
        with self._filtersMutex:
            self._filters = [f for f in self._filters if f != the_filter]


class FullyParallelEventReceivingStrategy(EventReceivingStrategy):
    """
    Dispatches events to multiple handlers that can be called in parallel.

    An :obj:`EventReceivingStrategy` that dispatches events to multiple
    handlers in individual threads in parallel. Each handler can be called
    in parallel for different requests.

    .. codeauthor:: jwienke
    """

    def __init__(self):
        self._logger = rsb.util.get_logger_by_class(self.__class__)
        self._filters = []
        self._mutex = threading.RLock()
        self._handlers = []

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
        self._logger.debug("Processing event %s", event)
        event.meta_data.set_deliver_time()
        workers = []
        with self._mutex:
            for h in self._handlers:
                workers.append(self.Worker(h, event, list(self._filters)))
        for w in workers:
            w.start()

    def add_handler(self, handler, wait):
        # We can ignore wait since the pool implements the desired
        # behavior.
        with self._mutex:
            self._handlers.append(handler)

    def remove_handler(self, handler, wait):
        # TODO anything required to implement wait functionality?
        with self._mutex:
            self._handlers.remove(handler)

    def add_filter(self, f):
        with self._mutex:
            self._filters.append(f)

    def remove_filter(self, the_filter):
        with self._mutex:
            self._filters = [f for f in self._filters if f != the_filter]


class NonQueuingParallelEventReceivingStrategy(EventReceivingStrategy):
    """
    Dispatches events to handlers using a single thread and no queues.

    An :obj:`EventReceivingStrategy` that dispatches events to multiple
    handlers using a single thread and without queuing. Only a single buffer
    is used to decouple the transport from the registered handlers. In case
    the handler processing is slower than the transport, the transport will
    block on inserting events into this strategy. Callers must ensure that they
    are in no active call for #handle when deactivating this instance.

    .. codeauthor:: jwienke
    """

    def __init__(self):
        self._logger = rsb.util.get_logger_by_class(self.__class__)
        self._filters = []
        self._mutex = threading.RLock()
        self._handlers = []
        self._queue = queue.Queue(1)
        self._interrupted = False
        self._thread = threading.Thread(target=self._work)
        self._thread.start()

    def deactivate(self):
        self._interrupted = True
        self._queue.put(None, True)
        self._thread.join()

    def _work(self):

        while True:

            event = self._queue.get(True)
            # interruption checking is handled here and not in the head of the
            # loop since we need put an artificial item into the queue when
            # deactivating this strategy and this item must never receive at
            # any handler
            if self._interrupted:
                return

            with self._mutex:
                for f in self._filters:
                    if not f.match(event):
                        return
                for handler in self._handlers:
                    handler(event)

    def handle(self, event):
        self._logger.debug("Processing event %s", event)
        event.meta_data.set_deliver_time()
        self._queue.put(event, True)

    def add_handler(self, handler, wait):
        with self._mutex:
            self._handlers.append(handler)

    def remove_handler(self, handler, wait):
        with self._mutex:
            self._handlers.remove(handler)

    def add_filter(self, f):
        with self._mutex:
            self._filters.append(f)

    def remove_filter(self, the_filter):
        with self._mutex:
            self._filters = [f for f in self._filters if f != the_filter]


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
        self._connectors = []

    @property
    def connectors(self):
        return self._connectors

    def add_connector(self, connector):
        self._connectors.append(connector)

    def remove_connector(self, connector):
        self._connectors.remove(connector)

    def handle(self, event):
        for connector in self._connectors:
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
        self._logger = rsb.util.get_logger_by_class(self.__class__)

        self._scope = None
        if connectors is None:
            self._connectors = []
        else:
            self._connectors = copy.copy(connectors)
        self._active = False

    def __del__(self):
        self._logger.debug("Destructing Configurator")
        if self._active:
            self.deactivate()

    @property
    def scope(self):
        return self._scope

    @scope.setter
    def scope(self, scope):
        """
        Define the scope the in route has to be set up.

        This will be called before calling #activate.

        Args:
            scope (rsb.Scope):
                the scope of the in route
        """
        self._scope = scope
        self._logger.debug("Got new scope %s", scope)
        for connector in self.connectors:
            connector.scope = scope

    @property
    def connectors(self):
        return self._connectors

    @property
    def transport_urls(self):
        """
        Return the transport URLs of all used connectors.

        Returns:
            list:
                List of transport URLs.
        """
        return {x.get_transport_url() for x in self._connectors}

    @property
    def active(self):
        return self._active

    def activate(self):
        if self._active:
            raise RuntimeError("Configurator is already active")

        self._logger.info("Activating configurator")
        for connector in self.connectors:
            connector.activate()

        self._active = True

    def deactivate(self):
        if not self._active:
            raise RuntimeError("Configurator is not active")

        self._logger.info("Deactivating configurator")
        for connector in self.connectors:
            connector.deactivate()

        self._active = False

    def set_quality_of_service_spec(self, qos):
        for connector in self.connectors:
            connector.quality_of_service_spec = qos


class InRouteConfigurator(Configurator):
    """
    Manages event receiving using a push strategy.

    Instances of this class manage the receiving, filtering and
    dispatching of events via one or more :obj:`rsb.transport.Connector` s
    and an :obj:`EventReceivingStrategy`.

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

        self._logger = rsb.util.get_logger_by_class(self.__class__)

        if receiving_strategy is None:
            self._receiving_strategy = ParallelEventReceivingStrategy()
        else:
            self._receiving_strategy = receiving_strategy

        for connector in self.connectors:
            connector.set_observer_action(self._receiving_strategy.handle)

    def deactivate(self):
        super().deactivate()

        for connector in self.connectors:
            connector.set_observer_action(None)
        self._receiving_strategy.deactivate()

    def handler_added(self, handler, wait):
        self._receiving_strategy.add_handler(handler, wait)

    def handler_removed(self, handler, wait):
        self._receiving_strategy.remove_handler(handler, wait)

    def filter_added(self, the_filter):
        self._receiving_strategy.add_filter(the_filter)
        for connector in self.connectors:
            connector.filter_notify(the_filter, rsb.filter.FilterAction.ADD)

    def filter_removed(self, the_filter):
        self._receiving_strategy.remove_filter(the_filter)
        for connector in self.connectors:
            connector.filter_notify(the_filter, rsb.filter.FilterAction.REMOVE)


class OutRouteConfigurator(Configurator):
    """
    Manages send events using one or more connectors and a sending strategy.

    Instances of this class manage the sending of events via one or
    more :obj:`rsb.transport.Connector` s and an :obj:`EventSendingStrategy`.

    .. codeauthor:: jmoringe
    """

    def __init__(self, connectors=None, sending_strategy=None):
        self._logger = rsb.util.get_logger_by_class(self.__class__)

        super().__init__(connectors)

        if sending_strategy is None:
            self._sending_strategy = DirectEventSendingStrategy()
        else:
            self._sending_strategy = sending_strategy

        if connectors is not None:
            list(map(self._sending_strategy.add_connector, connectors))

    def handle(self, event):
        if not self.active:
            raise RuntimeError("Trying to publish event on Configurator "
                               "which is not active.")

        self._logger.debug("Publishing event: %s", event)
        self._sending_strategy.handle(event)
