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

import time

from rsb import Event, Scope
from rsb.transport.local import (Bus,
                                 InConnector,
                                 OutConnector)
from rsb.transport.transporttest import TransportCheck


class StubSink:

    def __init__(self, scope):
        self.scope = scope
        self.events = []

    def scope(self):
        return self.scope

    def handle(self, event):
        self.events.append(event)

    def __call__(self, event):
        self.handle(event)


class TestBus:

    def test_construction(self):
        Bus()

    def test_notify_hierarchy(self):
        bus = Bus()

        target_scope = Scope("/this/is/a/test")
        scopes = target_scope.super_scopes(True)
        sinks_by_scope = {}
        for scope in scopes:
            sinks_by_scope[scope] = StubSink(scope)
            bus.add_sink(sinks_by_scope[scope])

        not_notified_sibling_sink = StubSink(Scope("/not/notified"))
        bus.add_sink(not_notified_sibling_sink)
        not_notified_child_sink = StubSink(
            target_scope.concat(Scope("/child")))
        bus.add_sink(not_notified_child_sink)

        event = Event(scope=target_scope)
        bus.handle(event)
        for scope, sink in list(sinks_by_scope.items()):
            assert event in sink.events
            assert len(sink.events) == 1


class TestOutConnector:

    def test_construction(self):
        OutConnector()

    def test_handle(self):

        bus = Bus()
        connector = OutConnector(bus=bus)

        scope = Scope("/a/test")
        sink = StubSink(scope)
        bus.add_sink(sink)

        e = Event()
        e.scope = scope

        before = time.time()
        connector.handle(e)
        after = time.time()
        assert len(sink.events) == 1
        assert e in sink.events
        assert e.meta_data.send_time >= before
        assert e.meta_data.send_time <= after


class TestInConnector:

    def test_construction(self):
        InConnector()

    def test_pass_to_action(self):

        scope = Scope("/lets/go")

        bus = Bus()
        connector = InConnector(bus=bus)
        connector.scope = scope
        connector.activate()

        action = StubSink(scope)
        connector.set_observer_action(action)

        e = Event()
        e.scope = scope
        bus.handle(e)
        assert len(action.events) == 1
        assert e in action.events


class TestLocalTransport(TransportCheck):

    def _get_in_connector(self, scope, activate=True):
        connector = InConnector()
        connector.scope = scope
        if activate:
            connector.activate()
        return connector

    def _get_out_connector(self, scope, activate=True):
        connector = OutConnector()
        connector.scope = scope
        if activate:
            connector.activate()
        return connector
