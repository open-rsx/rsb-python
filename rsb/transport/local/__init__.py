# ============================================================
#
# Copyright (C) 2012 by Johannes Wienke
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
Contains a highly efficient in-process transport implementation.

This transport allows participants inside one python process to communicate
without serialization overhead.

.. codeauthor:: jwienke
"""

import os
import platform
from threading import RLock

from rsb import transport


class Bus:
    """
    Singleton-like representation of the local bus.

    .. codeauthor:: jwienke
    """

    def __init__(self):
        self._mutex = RLock()
        self._sinks_by_scope = {}

    def add_sink(self, sink):
        """
        Add a sink for events pushed to the Bus.

        Args:
            sink:
                the sink to add
        """
        with self._mutex:
            # ensure that there is a list of sinks for the given scope
            if sink.scope not in self._sinks_by_scope:
                self._sinks_by_scope[sink.scope] = []
            self._sinks_by_scope[sink.scope].append(sink)

    def remove_sink(self, sink):
        """
        Remove a sink to not be notified anymore.

        Args:
            sink:
                sink to remove
        """
        with self._mutex:
            # return immediately if there is no such scope known for sinks
            if sink.scope not in self._sinks_by_scope:
                return
            self._sinks_by_scope[sink.scope].remove(sink)

    def handle(self, event):
        """
        Dispatches the provided event to all sinks of the appropriate scope.

        Args:
            event (rsb.Event):
                event to dispatch
        """

        with self._mutex:

            for scope, sink_list in list(self._sinks_by_scope.items()):
                if scope == event.scope or scope.is_super_scope_of(
                        event.scope):
                    for sink in sink_list:
                        sink.handle(event)

    def get_transport_url(self):
        hostname = platform.node().split('.')[0]
        pid = os.getpid()
        return 'inprocess://' + hostname + ':' + str(pid)


global_bus = Bus()


class OutConnector(transport.OutConnector):
    """
    In-process OutConnector.

    .. codeauthor:: jwienke
    """

    def __init__(
            self, bus=global_bus, converters=None, options=None, **kwargs):
        super().__init__(wire_type=object, **kwargs)
        self._bus = bus

    def handle(self, event):
        event.meta_data.set_send_time()
        self._bus.handle(event)

    def activate(self):
        pass

    def deactivate(self):
        pass

    def set_quality_of_service_spec(self, qos):
        pass

    def get_transport_url(self):
        return self._bus.get_transport_url()


class InConnector(transport.InConnector):
    """
    InConnector for the local transport.

    .. codeauthor:: jwienke
    """

    def __init__(
            self, bus=global_bus, converters=None, options=None, **kwargs):
        super().__init__(wire_type=object, **kwargs)
        self._bus = bus
        self._observer_action = None

    def filter_notify(self, filter_, action):
        pass

    def set_observer_action(self, action):
        self._observer_action = action

    def activate(self):
        assert self.scope is not None
        self._bus.add_sink(self)

    def deactivate(self):
        self._bus.remove_sink(self)

    def set_quality_of_service_spec(self, qos):
        pass

    def handle(self, event):
        # get reference which will survive parallel changes to the action
        event.meta_data.set_receive_time()
        action = self._observer_action
        if action is not None:
            action(event)

    def get_transport_url(self):
        return self._bus.get_transport_url()


class TransportFactory(transport.TransportFactory):
    """
    :obj:`TransportFactory` implementation for the local transport.

    .. codeauthor:: jwienke
    """

    @property
    def name(self):
        return "inprocess"

    @property
    def remote(self):
        return False

    def create_in_connector(self, converters, options):
        return InConnector(converters=converters, options=options)

    def create_out_connector(self, converters, options):
        return OutConnector(converters=converters, options=options)


def initialize():
    try:
        transport.register_transport(TransportFactory())
    except ValueError:
        pass
