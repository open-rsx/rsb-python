# ============================================================
#
# Copyright (C) 2010 by Johannes Wienke <jwienke at techfak dot uni-bielefeld dot de>
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

import unittest
import rsb.transport

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

        router = rsb.transport.Router(ActivateCountingPort(), ActivateCountingPort())
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

        router = rsb.transport.Router(DeactivateCountingPort(), DeactivateCountingPort())
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

        router = rsb.transport.Router(PublishCheckRouter(), PublishCheckRouter())

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
        router = rsb.transport.Router(ip, op)

        f1 = 12
        f2 = 24
        f3 = 36
        f4 = 48
        subscription = rsb.Subscription()
        subscription.appendFilter(f1)
        subscription.appendFilter(f2)

        router.subscribe(subscription)
        self.assertEqual(2, len(ip.filterCalls))
        self.assertTrue((f1, rsb.filter.FilterAction.ADD) in ip.filterCalls)
        self.assertTrue((f2, rsb.filter.FilterAction.ADD) in ip.filterCalls)

        subscription = rsb.Subscription()
        subscription.appendFilter(f3)
        subscription.appendFilter(f4)

        router.subscribe(subscription)
        self.assertEqual(4, len(ip.filterCalls))
        self.assertTrue((f3, rsb.filter.FilterAction.ADD) in ip.filterCalls)
        self.assertTrue((f4, rsb.filter.FilterAction.ADD) in ip.filterCalls)

        router.unsubscribe(subscription)
        self.assertEqual(6, len(ip.filterCalls))
        self.assertTrue((f3, rsb.filter.FilterAction.REMOVE) in ip.filterCalls)
        self.assertTrue((f4, rsb.filter.FilterAction.REMOVE) in ip.filterCalls)

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(RouterTest))
    return suite
