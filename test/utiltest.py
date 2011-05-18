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

import rsb.util
from threading import Condition
import time
import random
from rsb.util import OrderedQueueDispatcherPool
import logging

class EnumValueTest(unittest.TestCase):

    def testCompare(self):

        val1 = rsb.util.Enum.EnumValue("TEST")
        val2 = rsb.util.Enum.EnumValue("OTHER")
        self.assertNotEqual(val1, val2)

        self.assertTrue(val1 > val2)
        self.assertTrue(val1 >= val2)
        self.assertFalse(val1 < val2)
        self.assertFalse(val1 <= val2)

        val2 = rsb.util.Enum.EnumValue("TEST")
        self.assertEqual(val1, val2)

        val1 = rsb.util.Enum.EnumValue("TEST", 5)
        val2 = rsb.util.Enum.EnumValue("OTHER", 10)
        self.assertFalse(val1 > val2)
        self.assertFalse(val1 >= val2)
        self.assertTrue(val1 < val2)
        self.assertTrue(val1 <= val2)

    def testStr(self):

        self.assertEqual("TEST", str(rsb.util.Enum.EnumValue("TEST")))

class EnumTest(unittest.TestCase):

    def testEnum(self):

        e = rsb.util.Enum("e", ["A", "B", "C"])

        self.assertEqual(rsb.util.Enum.EnumValue("A"), e.A)
        self.assertEqual(rsb.util.Enum.EnumValue("B"), e.B)
        self.assertEqual(rsb.util.Enum.EnumValue("C"), e.C)

        self.assertEqual("Enum e: A, B, C", str(e))

    def testValueEnum(self):

        e = rsb.util.Enum("e", ["A", "B", "C"], [10, 20, 30])

        self.assertEqual(rsb.util.Enum.EnumValue("A", 10), e.A)
        self.assertEqual(rsb.util.Enum.EnumValue("B", 20), e.B)
        self.assertEqual(rsb.util.Enum.EnumValue("C", 30), e.C)

class OrderedQueueDispatcherPoolTest(unittest.TestCase):

    def setUp(self):
        logging.basicConfig()
        logging.getLogger().setLevel(logging.DEBUG)

    class StubReciever(object):

        nextReceiverNum = 1
        @classmethod
        def nextNumber(cls):
            num = cls.nextReceiverNum
            cls.nextReceiverNum = cls.nextReceiverNum + 1
            return num

        def __init__(self):
            self.receiverNum = self.nextNumber()
            self.condition = Condition()
            self.messages = []

        def __str__(self):
            return "StubReceiver%d" % self.receiverNum

    def deliver(self, receiver, message):

        with receiver.condition:

            time.sleep(random.random() * 0.05 * float((receiver.receiverNum % 10)))

            receiver.messages.append(message)
            receiver.condition.notify_all()

    def testProcessing(self):

        numMessages = 10
        pool = OrderedQueueDispatcherPool(4, self.deliver)

        numReceivers = 11
        receivers = []
        for i in range(numReceivers):
            r = self.StubReciever()
            pool.registerReceiver(r)
            receivers.append(r)

        pool.start()
        try:
            pool.start()
            self.fail("Starting an already running pool must not be possible")
        except RuntimeError:
            pass

        # start jobs
        for i in range(numMessages):
            pool.push(i)

        # wait for processing
        for receiver in receivers:
            with receiver.condition:
                while len(receiver.messages) < numMessages:
                    receiver.condition.wait()

        pool.stop()

        # check receivers
        for receiver in receivers:

            self.assertEqual(numMessages, len(receiver.messages))

            for i in range(numMessages):
                self.assertEqual(i, receiver.messages[i])

    class RejectFilter(object):

        def __init__(self):
            self.rejectCalls = 0
            self.condition = Condition()

        def __call__(self, receiver, message):
            with self.condition:
                self.rejectCalls = self.rejectCalls + 1
                self.condition.notify_all();
                return False

    def testFilterExecution(self):

        filter = self.RejectFilter()
        pool = OrderedQueueDispatcherPool(2, self.deliver, filter)

        receiver = self.StubReciever()
        pool.registerReceiver(receiver)

        pool.start()

        numMessages = 10;
        for i in range(numMessages):
            pool.push(i)

        # wait for filtering
        with filter.condition:
            while filter.rejectCalls < numMessages:
                filter.condition.wait()

        pool.stop()

        self.assertEqual(numMessages, filter.rejectCalls)

    def testUnregister(self):

        pool = OrderedQueueDispatcherPool(2, self.deliver)

        pool.start()

        receiver = self.StubReciever()
        pool.registerReceiver(receiver)
        self.assertTrue(pool.unregisterReceiver(receiver))
        self.assertFalse(pool.unregisterReceiver(receiver))

        pool.push(42)

        pool.stop()

        time.sleep(0.1)

        self.assertEqual(0, len(receiver.messages))

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(EnumValueTest))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(EnumTest))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(OrderedQueueDispatcherPoolTest))
    return suite
