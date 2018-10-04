# ============================================================
#
# Copyright (C) 2012 by Johannes Wienke <jwienke at techfak dot uni-bielefeld dot de>
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
This package contains a highly efficient in-process transport implementation
which allows participants inside one python process to communicate without
serialization overhead.

.. codeauthor:: jwienke
"""

import os
import platform
from threading import RLock
import queue

from rsb import transport


class Bus(object):
    """
    Singleton-like representation of the local bus.

    .. codeauthor:: jwienke
    """

    def __init__(self):
        self.__mutex = RLock()
        self.__sinks_by_scope = {}

    def add_sink(self, sink):
        """
        Adds a sink for events pushed to the Bus.

        Args:
            sink:
                the sink to add
        """
        with self.__mutex:
            # ensure that there is a list of sinks for the given scope
            if sink.get_scope() not in self.__sinks_by_scope:
                self.__sinks_by_scope[sink.get_scope()] = []
            self.__sinks_by_scope[sink.get_scope()].append(sink)

    def remove_sink(self, sink):
        """
        Removes a sink to not be notified anymore.

        Args:
            sink:
                sink to remove
        """
        with self.__mutex:
            # return immediately if there is no such scope known for sinks
            if sink.get_scope() not in self.__sinks_by_scope:
                return
            self.__sinks_by_scope[sink.get_scope()].remove(sink)

    def handle(self, event):
        """
        Dispatches the provided event to all sinks of the appropriate scope.

        Args:
            event (rsb.Event):
                event to dispatch
        """

        with self.__mutex:

            for scope, sink_list in list(self.__sinks_by_scope.items()):
                if scope == event.scope or scope.is_super_scope_of(event.scope):
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

    def __init__(self, bus=global_bus, converters=None, options=None, **kwargs):
        transport.OutConnector.__init__(self, wire_type=object, **kwargs)
        self.__bus = bus

    def handle(self, event):
        event.meta_data.set_send_time()
        self.__bus.handle(event)

    def activate(self):
        pass

    def deactivate(self):
        pass

    def set_quality_of_service_spec(self, qos):
        pass

    def get_transport_url(self):
        return self.__bus.get_transport_url()


class InPushConnector(transport.InPushConnector):
    """
    InPushConnector for the local transport.

    .. codeauthor:: jwienke
    """

    def __init__(self, bus=global_bus, converters=None, options=None, **kwargs):
        transport.InPushConnector.__init__(self, wire_type=object, **kwargs)
        self.__bus = bus
        self.__scope = None
        self.__observer_action = None

    def filter_notify(self, filter, action):
        pass

    def set_observer_action(self, action):
        self.__observer_action = action

    def set_scope(self, scope):
        self.__scope = scope

    def get_scope(self):
        return self.__scope

    def activate(self):
        assert self.__scope is not None
        self.__bus.add_sink(self)

    def deactivate(self):
        self.__bus.remove_sink(self)

    def set_quality_of_service_spec(self, qos):
        pass

    def handle(self, event):
        # get reference which will survive parallel changes to the action
        event.meta_data.set_receive_time()
        action = self.__observer_action
        if action is not None:
            action(event)

    def get_transport_url(self):
        return self.__bus.get_transport_url()


class InPullConnector(transport.InPullConnector):

    def __init__(self, bus=global_bus, converters=None, options=None, **kwargs):
        transport.InPullConnector.__init__(self, wire_type=object, **kwargs)
        self.__bus = bus
        self.__scope = None
        self.__event_queue = queue.Queue()

    def set_scope(self, scope):
        self.__scope = scope

    def get_scope(self):
        return self.__scope

    def activate(self):
        assert self.__scope is not None
        self.__bus.add_sink(self)

    def deactivate(self):
        self.__bus.remove_sink(self)

    def set_quality_of_service_spec(self, qos):
        pass

    def handle(self, event):
        event.meta_data.set_receive_time()
        self.__event_queue.put(event)

    def raise_event(self, block):
        try:
            return self.__event_queue.get(block)
        except queue.Empty:
            return None


class TransportFactory(transport.TransportFactory):
    """
    :obj:`TransportFactory` implementation for the local transport.

    .. codeauthor:: jwienke
    """

    def get_name(self):
        return "inprocess"

    def is_remote(self):
        return False

    def create_in_push_connector(self, converters, options):
        return InPushConnector(converters=converters, options=options)

    def create_in_pull_connector(self, converters, options):
        return InPullConnector(converters=converters, options=options)

    def create_out_connector(self, converters, options):
        return OutConnector(converters=converters, options=options)


def initialize():
    try:
        transport.register_transport(TransportFactory())
    except ValueError:
        pass
