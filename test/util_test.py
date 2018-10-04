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

import random
from threading import Condition
import time
import unittest

import rsb.util
from rsb.util import OrderedQueueDispatcherPool


class EnumValueTest(unittest.TestCase):

    def test_compare(self):

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

    def test_str(self):

        self.assertEqual("TEST", str(rsb.util.Enum.EnumValue("TEST")))


class EnumTest(unittest.TestCase):

    def test_enum(self):

        e = rsb.util.Enum("e", ["A", "B", "C"])

        self.assertEqual(rsb.util.Enum.EnumValue("A"), e.A)
        self.assertEqual(rsb.util.Enum.EnumValue("B"), e.B)
        self.assertEqual(rsb.util.Enum.EnumValue("C"), e.C)

        self.assertEqual("Enum e: A, B, C", str(e))

    def test_value_enum(self):

        e = rsb.util.Enum("e", ["A", "B", "C"], [10, 20, 30])

        self.assertEqual(rsb.util.Enum.EnumValue("A", 10), e.A)
        self.assertEqual(rsb.util.Enum.EnumValue("B", 20), e.B)
        self.assertEqual(rsb.util.Enum.EnumValue("C", 30), e.C)

    def test_from_string(self):
        e = rsb.util.Enum("e", ["A", "B", "C"], [10, 20, 30])
        self.assertEqual(e.from_string('A'), e.A)
        self.assertEqual(e.from_string('B'), e.B)
        self.assertEqual(e.from_string('C'), e.C)
        self.assertRaises(ValueError, e.from_string, 'D')


class OrderedQueueDispatcherPoolTest(unittest.TestCase):

    class StubReciever(object):

        next_receiver_num = 1

        @classmethod
        def next_number(cls):
            num = cls.next_receiver_num
            cls.next_receiver_num = cls.next_receiver_num + 1
            return num

        def __init__(self):
            self.receiver_num = self.next_number()
            self.condition = Condition()
            self.messages = []

        def __str__(self):
            return "StubReceiver%d" % self.receiver_num

    def deliver(self, receiver, message):

        with receiver.condition:

            time.sleep(random.random() * 0.05 *
                       float((receiver.receiver_num % 10)))

            receiver.messages.append(message)
            receiver.condition.notify_all()

    def test_processing(self):

        num_messages = 10
        pool = OrderedQueueDispatcherPool(4, self.deliver)

        num_receivers = 11
        receivers = []
        for i in range(num_receivers):
            r = self.StubReciever()
            pool.register_receiver(r)
            receivers.append(r)

        pool.start()
        try:
            pool.start()
            self.fail("Starting an already running pool must not be possible")
        except RuntimeError:
            pass

        # start jobs
        for i in range(num_messages):
            pool.push(i)

        # wait for processing
        for receiver in receivers:
            with receiver.condition:
                while len(receiver.messages) < num_messages:
                    receiver.condition.wait()

        pool.stop()

        # check receivers
        for receiver in receivers:

            self.assertEqual(num_messages, len(receiver.messages))

            for i in range(num_messages):
                self.assertEqual(i, receiver.messages[i])

    class RejectFilter(object):

        def __init__(self):
            self.reject_calls = 0
            self.condition = Condition()

        def __call__(self, receiver, message):
            with self.condition:
                self.reject_calls = self.reject_calls + 1
                self.condition.notify_all()
                return False

    def test_filter_execution(self):

        reject_filter = self.RejectFilter()
        pool = OrderedQueueDispatcherPool(2, self.deliver, reject_filter)

        receiver = self.StubReciever()
        pool.register_receiver(receiver)

        pool.start()

        num_messages = 10
        for i in range(num_messages):
            pool.push(i)

        # wait for filtering
        with reject_filter.condition:
            while reject_filter.reject_calls < num_messages:
                reject_filter.condition.wait()

        pool.stop()

        self.assertEqual(num_messages, reject_filter.reject_calls)

    def test_unregister(self):

        pool = OrderedQueueDispatcherPool(2, self.deliver)

        pool.start()

        receiver = self.StubReciever()
        pool.register_receiver(receiver)
        self.assertTrue(pool.unregister_receiver(receiver))
        self.assertFalse(pool.unregister_receiver(receiver))

        pool.push(42)

        pool.stop()

        time.sleep(0.1)

        self.assertEqual(0, len(receiver.messages))
