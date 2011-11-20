# ============================================================
#
# Copyright (C) 2010 by Johannes Wienke <jwienke at techfak dot uni-bielefeld dot de>
#
# This program is free software you can redistribute it
# and/or modify it under the terms of the GNU General
# Public License as published by the Free Software Foundation
# either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# ============================================================

import uuid
import unittest

from rsb.eventprocessing import ParallelEventReceivingStrategy, Router
from threading import Condition
from rsb.filter import RecordingTrueFilter, RecordingFalseFilter
from rsb import Event, EventId
import rsb

class ParallelEventReceivingStrategyTest(unittest.TestCase):

    def testMatchingProcess(self):


        ep = ParallelEventReceivingStrategy(5)

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
        ep.addHandler(matchingAction1, wait = True)
        ep.addHandler(matchingAction2, wait = True)

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

    def testNotMatchingProcess(self):

        ep = ParallelEventReceivingStrategy(5)

        noMatchingCalls = []

        def noMatchingAction(event):
            noMatchingCalls.append(event)

        noMatchRecordingFilter = RecordingFalseFilter()
        ep.addFilter(noMatchRecordingFilter)
        ep.addHandler(noMatchingAction, wait = True)

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

    def testAddRemove(self):
        for size in xrange(2, 10):
            ep = ParallelEventReceivingStrategy(size)

            h1 = lambda e: e
            h2 = lambda e: e
            ep.addHandler(h1, wait = True)
            ep.addHandler(h2, wait = True)
            ep.addHandler(h1, wait = True)

            ep.handle(Event(EventId(uuid.uuid4(), 0)))
            ep.handle(Event(EventId(uuid.uuid4(), 1)))
            ep.handle(Event(EventId(uuid.uuid4(), 2)))

            ep.removeHandler(h1, wait = True)
            ep.removeHandler(h2, wait = True)
            ep.removeHandler(h1, wait = True)

class RouterTest(unittest.TestCase):

    def testActivate(self):

        class ActivateCountingPort(object):

            activations = 0

            def activate(self):
                ActivateCountingPort.activations = ActivateCountingPort.activations + 1

            def deactivate(self):
                pass

            def setObserverAction(self, action):
                pass

        router = Router(ActivateCountingPort(), ActivateCountingPort())
        self.assertEqual(0, ActivateCountingPort.activations)

        router.activate()
        self.assertEqual(2, ActivateCountingPort.activations)
        router.activate()
        self.assertEqual(2, ActivateCountingPort.activations)

    def testDeactivate(self):

        class DeactivateCountingPort(object):

            deactivations = 0

            def activate(self):
                pass

            def deactivate(self):
                DeactivateCountingPort.deactivations = DeactivateCountingPort.deactivations + 1

            def setObserverAction(self, action):
                pass

        router = Router(DeactivateCountingPort(), DeactivateCountingPort())
        self.assertEqual(0, DeactivateCountingPort.deactivations)

        router.deactivate()
        self.assertEqual(0, DeactivateCountingPort.deactivations)

        router.activate()
        self.assertEqual(0, DeactivateCountingPort.deactivations)
        router.deactivate()
        self.assertEqual(2, DeactivateCountingPort.deactivations)
        router.deactivate()
        self.assertEqual(2, DeactivateCountingPort.deactivations)

    def testPublish(self):

        class PublishCheckRouter(object):

            lastEvent = None

            def activate(self):
                pass
            def deactivate(self):
                pass

            def push(self, event):
                PublishCheckRouter.lastEvent = event

            def setObserverAction(self, action):
                pass

        router = Router(PublishCheckRouter(), PublishCheckRouter())

        event = 42
        router.publish(event)
        self.assertEqual(None, PublishCheckRouter.lastEvent)
        router.activate()
        router.publish(event)
        self.assertEqual(event, PublishCheckRouter.lastEvent)
        event = 34
        router.publish(event)
        self.assertEqual(event, PublishCheckRouter.lastEvent)

        PublishCheckRouter.lastEvent = None
        router.deactivate()
        router.publish(event)
        self.assertEqual(None, PublishCheckRouter.lastEvent)

    def testNotifyInPort(self):

        class SubscriptionTestPort(object):

            def __init__(self):
                self.activated = False
                self.deactivated = False
                self.filterCalls = []

            def activate(self):
                self.activated = True
            def deactivate(self):
                self.deactivated = True
            def filterNotify(self, filter, action):
                self.filterCalls.append((filter, action))
            def setObserverAction(self, action):
                pass

        ip = SubscriptionTestPort()
        op = SubscriptionTestPort()
        router = Router(ip, op)

        f1 = 12
        f2 = 24
        f3 = 36
        f4 = 48
        router.filterAdded(f1)
        router.filterAdded(f2)
        self.assertEqual(2, len(ip.filterCalls))
        self.assertTrue((f1, rsb.filter.FilterAction.ADD) in ip.filterCalls)
        self.assertTrue((f2, rsb.filter.FilterAction.ADD) in ip.filterCalls)

        router.filterAdded(f3)
        router.filterAdded(f4)

        self.assertEqual(4, len(ip.filterCalls))
        self.assertTrue((f3, rsb.filter.FilterAction.ADD) in ip.filterCalls)
        self.assertTrue((f4, rsb.filter.FilterAction.ADD) in ip.filterCalls)

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(ParallelEventReceivingStrategyTest))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(RouterTest))
    return suite
