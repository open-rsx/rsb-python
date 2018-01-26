# ============================================================
#
# Copyright (C) 2010 by Johannes Wienke <jwienke at techfak dot uni-bielefeld dot de>
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

import uuid
import unittest
from threading import Condition, Lock

from rsb.filter import RecordingTrueFilter, RecordingFalseFilter
from rsb import Event, EventId
import rsb
import rsb.eventprocessing
from rsb.eventprocessing import FullyParallelEventReceivingStrategy
import time


class ScopeDispatcherTest(unittest.TestCase):

    def testSinks(self):
        dispatcher = rsb.eventprocessing.ScopeDispatcher()
        dispatcher.addSink(rsb.Scope('/foo'), 1)
        dispatcher.addSink(rsb.Scope('/foo'), 2)
        dispatcher.addSink(rsb.Scope('/bar'), 3)
        self.assertEqual(set((1, 2, 3)), set(dispatcher.sinks))

    def testMatchingSinks(self):
        dispatcher = rsb.eventprocessing.ScopeDispatcher()
        dispatcher.addSink(rsb.Scope('/foo'), 1)
        dispatcher.addSink(rsb.Scope('/foo'), 2)
        dispatcher.addSink(rsb.Scope('/bar'), 3)

        def check(scope, expected):
            self.assertEqual(set(expected),
                             set(dispatcher.matchingSinks(rsb.Scope(scope))))
        check("/",        ())
        check("/foo",     (1, 2))
        check("/foo/baz", (1, 2))
        check("/bar",     (3,))
        check("/bar/fez", (3,))

class ParallelEventReceivingStrategyTest(unittest.TestCase):

    def testMatchingProcess(self):
        ep = rsb.eventprocessing.ParallelEventReceivingStrategy(5)

        mc1Cond = Condition()
        matchingCalls1 = []
        mc2Cond = Condition()
        matchingCalls2 = []

        def matchingAction1(event):
            with mc1Cond:
                matchingCalls1.append(event)
                mc1Cond.notifyAll()

        def matchingAction2(event):
            with mc2Cond:
                matchingCalls2.append(event)
                mc2Cond.notifyAll()

        matchingRecordingFilter1 = RecordingTrueFilter()
        matchingRecordingFilter2 = RecordingTrueFilter()
        ep.addFilter(matchingRecordingFilter1)
        ep.addFilter(matchingRecordingFilter2)
        ep.addHandler(matchingAction1, wait=True)
        ep.addHandler(matchingAction2, wait=True)

        event1 = Event(EventId(uuid.uuid4(), 0))
        event2 = Event(EventId(uuid.uuid4(), 1))

        ep.handle(event1)
        ep.handle(event2)

        # both filters must have been called
        with matchingRecordingFilter1.condition:
            while len(matchingRecordingFilter1.events) < 4:
                matchingRecordingFilter1.condition.wait()

            self.assertEqual(4, len(matchingRecordingFilter1.events))
            self.assertTrue(event1 in matchingRecordingFilter1.events)
            self.assertTrue(event2 in matchingRecordingFilter1.events)

        with matchingRecordingFilter2.condition:
            while len(matchingRecordingFilter2.events) < 4:
                matchingRecordingFilter2.condition.wait()

            self.assertEqual(4, len(matchingRecordingFilter2.events))
            self.assertTrue(event1 in matchingRecordingFilter2.events)
            self.assertTrue(event2 in matchingRecordingFilter2.events)

        # both actions must have been called
        with mc1Cond:
            while len(matchingCalls1) < 2:
                mc1Cond.wait()
            self.assertEqual(2, len(matchingCalls1))
            self.assertTrue(event1 in matchingCalls1)
            self.assertTrue(event2 in matchingCalls1)

        with mc2Cond:
            while len(matchingCalls2) < 2:
                mc2Cond.wait()
            self.assertEqual(2, len(matchingCalls2))
            self.assertTrue(event1 in matchingCalls2)
            self.assertTrue(event2 in matchingCalls2)

        ep.removeFilter(matchingRecordingFilter2)
        ep.removeFilter(matchingRecordingFilter1)

    def testNotMatchingProcess(self):

        ep = rsb.eventprocessing.ParallelEventReceivingStrategy(5)

        noMatchingCalls = []

        def noMatchingAction(event):
            noMatchingCalls.append(event)

        noMatchRecordingFilter = RecordingFalseFilter()
        ep.addFilter(noMatchRecordingFilter)
        ep.addHandler(noMatchingAction, wait=True)

        event1 = Event(EventId(uuid.uuid4(), 0))
        event2 = Event(EventId(uuid.uuid4(), 1))
        event3 = Event(EventId(uuid.uuid4(), 2))

        ep.handle(event1)
        ep.handle(event2)
        ep.handle(event3)

        # no Match listener must not have been called
        with noMatchRecordingFilter.condition:
            while len(noMatchRecordingFilter.events) < 3:
                noMatchRecordingFilter.condition.wait()
            self.assertEqual(3, len(noMatchRecordingFilter.events))
            self.assertTrue(event1 in noMatchRecordingFilter.events)
            self.assertTrue(event2 in noMatchRecordingFilter.events)
            self.assertTrue(event3 in noMatchRecordingFilter.events)

        self.assertEqual(0, len(noMatchingCalls))

        ep.removeFilter(noMatchRecordingFilter)

    def testAddRemove(self):
        for size in xrange(2, 10):
            ep = rsb.eventprocessing.ParallelEventReceivingStrategy(size)

            h1 = lambda e: e
            h2 = lambda e: e
            ep.addHandler(h1, wait=True)
            ep.addHandler(h2, wait=True)
            ep.addHandler(h1, wait=True)

            ep.handle(Event(EventId(uuid.uuid4(), 0)))
            ep.handle(Event(EventId(uuid.uuid4(), 1)))
            ep.handle(Event(EventId(uuid.uuid4(), 2)))

            ep.removeHandler(h1, wait=True)
            ep.removeHandler(h2, wait=True)
            ep.removeHandler(h1, wait=True)


class MockConnector(object):
    def activate(self):
        pass

    def deactivate(self):
        pass

    def push(self, event):
        pass

    def filterNotify(self, filter, action):
        pass

    def setObserverAction(self, action):
        pass


# TODO(jmoringe): could be useful in all tests for active objects
class ActivateCountingMockConnector(MockConnector):
    def __init__(self, case):
        self.__case = case
        self.activations = 0
        self.deactivations = 0

    def activate(self):
        self.activations += 1

    def deactivate(self):
        self.deactivations += 1

    def expect(self, activations, deactivations):
        self.__case.assertEqual(activations, self.activations)
        self.__case.assertEqual(deactivations, self.deactivations)


class OutRouteConfiguratorTest(unittest.TestCase):

    def testActivation(self):
        connector = ActivateCountingMockConnector(self)
        configurator = rsb.eventprocessing.OutRouteConfigurator(
            connectors=[connector])

        # Cannot deactivate inactive configurator
        self.assertRaises(RuntimeError, configurator.deactivate)
        connector.expect(0, 0)

        configurator.activate()
        connector.expect(1, 0)

        # Cannot activate already activated configurator
        self.assertRaises(RuntimeError, configurator.activate)
        connector.expect(1, 0)

        configurator.deactivate()
        connector.expect(1, 1)

        # Cannot deactivate twice
        self.assertRaises(RuntimeError, configurator.deactivate)
        connector.expect(1, 1)

    def testPublish(self):
        class RecordingOutConnector(MockConnector):
            lastEvent = None

            def handle(self, event):
                RecordingOutConnector.lastEvent = event

        configurator = rsb.eventprocessing.OutRouteConfigurator(
            connectors=[RecordingOutConnector()])

        event = 42

        # Cannot publish while inactive
        self.assertRaises(RuntimeError, configurator.handle, event)
        self.assertEqual(None, RecordingOutConnector.lastEvent)

        configurator.activate()
        configurator.handle(event)
        self.assertEqual(event, RecordingOutConnector.lastEvent)

        event = 34
        configurator.handle(event)
        self.assertEqual(event, RecordingOutConnector.lastEvent)

        # Deactivate and check exception, again
        RecordingOutConnector.lastEvent = None
        configurator.deactivate()
        self.assertRaises(RuntimeError, configurator.handle, event)
        self.assertEqual(None, RecordingOutConnector.lastEvent)


class InPushRouteConfiguratorTest(unittest.TestCase):

    def testActivation(self):
        connector = ActivateCountingMockConnector(self)
        configurator = rsb.eventprocessing.InPushRouteConfigurator(
            connectors=[connector])

        # Cannot deactivate inactive configurator
        self.assertRaises(RuntimeError, configurator.deactivate)
        connector.expect(0, 0)

        configurator.activate()
        connector.expect(1, 0)

        # Cannot activate already activated configurator
        self.assertRaises(RuntimeError, configurator.activate)
        connector.expect(1, 0)

        configurator.deactivate()
        connector.expect(1, 1)

        # Cannot deactivate twice
        self.assertRaises(RuntimeError, configurator.deactivate)
        connector.expect(1, 1)

    def testNotifyConnector(self):
        class RecordingMockConnector(MockConnector):
            def __init__(self):
                self.calls = []

            def filterNotify(self, filter, action):
                self.calls.append((filter, action))

            def expect(self1, calls):
                self.assertEqual(len(calls), len(self1.calls))
                for (expFilter, expAction), (filter, action) in \
                        zip(calls, self1.calls):
                    self.assertEqual(expFilter, filter)
                    if expAction == 'add':
                        self.assertEquals(action, rsb.filter.FilterAction.ADD)

        connector = RecordingMockConnector()
        configurator = rsb.eventprocessing.InPushRouteConfigurator(
            connectors=[connector])
        configurator.activate()
        connector.expect(())

        f1, f2, f3 = 12, 24, 36
        configurator.filterAdded(f1)
        connector.expect(((f1, 'add'),))

        configurator.filterAdded(f2)
        connector.expect(((f1, 'add'), (f2, 'add')))

        configurator.filterAdded(f3)
        connector.expect(((f1, 'add'), (f2, 'add'), (f3, 'add')))

        configurator.filterRemoved(f3)
        connector.expect(((f1, 'add'), (f2, 'add'), (f3, 'add'),
                          (f3, 'remove')))


class FullyParallelEventReceivingStrategyTest(unittest.TestCase):

    class CollectingHandler(object):

        def __init__(self):
            self.condition = Condition()
            self.event = None

        def __call__(self, event):
            with self.condition:
                self.event = event
                self.condition.notifyAll()

    def testSmoke(self):

        strategy = FullyParallelEventReceivingStrategy()

        h1 = self.CollectingHandler()
        h2 = self.CollectingHandler()
        strategy.addHandler(h1, True)
        strategy.addHandler(h2, True)

        event = Event(id=42)
        strategy.handle(event)

        with h1.condition:
            while h1.event is None:
                h1.condition.wait()
            self.assertEqual(event, h1.event)

        with h2.condition:
            while h2.event is None:
                h2.condition.wait()
            self.assertEqual(event, h2.event)

    def testFiltering(self):

        strategy = FullyParallelEventReceivingStrategy()

        falseFilter = RecordingFalseFilter()
        strategy.addFilter(falseFilter)

        handler = self.CollectingHandler()
        strategy.addHandler(handler, True)

        event = Event(id=42)
        strategy.handle(event)

        with falseFilter.condition:
            while len(falseFilter.events) == 0:
                falseFilter.condition.wait(timeout=5)
                if len(falseFilter.events) == 0:
                    self.fail("Filter not called")

        time.sleep(1)

        with handler.condition:
            self.assertEqual(None, handler.event)

        strategy.removeFilter(falseFilter)

    def testParallelCallOfOneHandler(self):

        class Counter(object):
            def __init__(self):
                self.value = 0
        maxParallelCalls = Counter()
        currentCalls = []
        callLock = Condition()

        class Receiver(object):

            def __init__(self, counter):
                self.counter = counter

            def __call__(self, message):
                with callLock:
                    currentCalls.append(message)
                    self.counter.value = max(self.counter.value,
                                             len(currentCalls))
                    callLock.notifyAll()
                time.sleep(2)
                with callLock:
                    currentCalls.remove(message)
                    callLock.notifyAll()

        strategy = FullyParallelEventReceivingStrategy()
        strategy.addHandler(Receiver(maxParallelCalls), True)

        event = Event(id=42)
        strategy.handle(event)
        event = Event(id=43)
        strategy.handle(event)
        event = Event(id=44)
        strategy.handle(event)

        numCalled = 0
        with callLock:
            while maxParallelCalls.value < 3 and numCalled < 5:
                numCalled = numCalled + 1
                callLock.wait()
            if numCalled == 5:
                self.fail("Impossible to be called in parallel again")
            else:
                self.assertEqual(3, maxParallelCalls.value)
