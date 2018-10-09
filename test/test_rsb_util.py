# ============================================================
#
# Copyright (C) 2010 by Johannes Wienke
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

import random
from threading import Condition
import time

import pytest

from rsb.util import OrderedQueueDispatcherPool


class TestOrderedQueueDispatcherPool:

    class StubReciever:

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
            pytest.fail(
                "Starting an already running pool must not be possible")
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

            assert len(receiver.messages) == num_messages

            for i in range(num_messages):
                assert receiver.messages[i] == i

    class RejectFilter:

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

        assert reject_filter.reject_calls == num_messages

    def test_unregister(self):

        pool = OrderedQueueDispatcherPool(2, self.deliver)

        pool.start()

        receiver = self.StubReciever()
        pool.register_receiver(receiver)
        assert pool.unregister_receiver(receiver)
        assert not pool.unregister_receiver(receiver)

        pool.push(42)

        pool.stop()

        time.sleep(0.1)

        assert len(receiver.messages) == 0
