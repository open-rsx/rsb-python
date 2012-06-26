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

    def testFromString(self):
         e = rsb.util.Enum("e", ["A", "B", "C"], [10, 20, 30])
         self.assertEqual(e.fromString('A'), e.A)
         self.assertEqual(e.fromString('B'), e.B)
         self.assertEqual(e.fromString('C'), e.C)
         self.assertRaises(ValueError, e.fromString, 'D')

class OrderedQueueDispatcherPoolTest(unittest.TestCase):

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
