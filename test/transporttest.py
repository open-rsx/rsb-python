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

import abc
import random
import string
import threading
import time
import uuid

import pytest

import rsb
from rsb import (create_informer,
                 create_listener,
                 create_reader,
                 Event,
                 EventId,
                 Scope)


class SettingReceiver:

    def __init__(self, scope):
        self.result_event = None
        self.result_condition = threading.Condition()
        self.scope = scope

    def __call__(self, event):
        with self.result_condition:
            self.result_event = event
            self.result_condition.notifyAll()

    def __repr__(self):
        return "{}({!r})".format(self.__class__.__name__, self.scope)


class TransportCheck(metaclass=abc.ABCMeta):
    """
    An abstract base class for ensuring interface assumptions about transports.

    .. codeauthor:: jwienke
    """

    @abc.abstractmethod
    def _get_in_push_connector(self, scope, activate=True):
        pass

    @abc.abstractmethod
    def _get_in_pull_connector(self, scope, activate=True):
        pass

    @abc.abstractmethod
    def _get_out_connector(self, scope, activate=True):
        pass

    @pytest.mark.timeout(5)
    def test_roundtrip(self):

        good_scope = Scope("/good")

        inconnector = self._get_in_push_connector(good_scope)
        outconnector = self._get_out_connector(good_scope)

        receiver = SettingReceiver(good_scope)
        inconnector.set_observer_action(receiver)

        # first an event that we do not want
        event = Event(EventId(uuid.uuid4(), 0))
        event.scope = Scope("/notGood")
        event.data = "dummy data"
        event.data_type = str
        event.meta_data.sender_id = uuid.uuid4()
        outconnector.handle(event)

        # and then a desired event
        event.scope = good_scope
        outconnector.handle(event)

        with receiver.result_condition:
            while receiver.result_event is None:
                receiver.result_condition.wait(10)
            assert receiver.result_event
            # ignore meta data here
            event.set_meta_data(None)
            receiver.result_event.set_meta_data(None)
            assert receiver.result_event == event

        inconnector.deactivate()
        outconnector.deactivate()

    @pytest.mark.timeout(5)
    def test_pull_non_blocking(self):
        try:
            inconnector = self._get_in_pull_connector(Scope("/somewhere"))
        except NotImplementedError:
            return

        received = inconnector.raise_event(False)
        assert received is None

        inconnector.deactivate()

    @pytest.mark.timeout(5)
    def test_pull_roundtrip(self):

        good_scope = Scope("/good")

        try:
            inconnector = self._get_in_pull_connector(good_scope)
        except NotImplementedError:
            return
        outconnector = self._get_out_connector(good_scope)

        # first an event that we do not want
        event = Event(EventId(uuid.uuid4(), 0))
        event.scope = Scope("/notGood")
        event.data = "dummy data"
        event.data_type = str
        event.meta_data.sender_id = uuid.uuid4()
        outconnector.handle(event)

        # and then a desired event
        event.scope = good_scope
        outconnector.handle(event)

        received = inconnector.raise_event(True)
        # ignore meta data here
        event.set_meta_data(None)
        received.set_meta_data(None)
        assert received == event

        inconnector.deactivate()
        outconnector.deactivate()

    @pytest.mark.timeout(5)
    def test_user_roundtrip(self):
        scope = Scope("/test/it")
        in_connector = self._get_in_push_connector(scope, activate=False)
        out_connector = self._get_out_connector(scope, activate=False)

        out_configurator = rsb.eventprocessing.OutRouteConfigurator(
            connectors=[out_connector])
        in_configurator = rsb.eventprocessing.InPushRouteConfigurator(
            connectors=[in_connector])

        publisher = create_informer(scope,
                                    data_type=str,
                                    configurator=out_configurator)
        listener = create_listener(scope, configurator=in_configurator)

        receiver = SettingReceiver(scope)
        listener.add_handler(receiver)

        data1 = "a string to test"
        sent_event = Event(EventId(uuid.uuid4(), 0))
        sent_event.set_data(data1)
        sent_event.set_data_type(str)
        sent_event.set_scope(scope)
        sent_event.get_meta_data().set_user_info("test", "it")
        sent_event.get_meta_data().set_user_info("test again", "it works?")
        sent_event.get_meta_data().set_user_time("blubb", 234234.0)
        sent_event.get_meta_data().set_user_time("bla", 3434343.45)
        sent_event.add_cause(EventId(uuid.uuid4(), 1323))
        sent_event.add_cause(EventId(uuid.uuid4(), 42))

        publisher.publish_event(sent_event)

        with receiver.result_condition:
            while receiver.result_event is None:
                receiver.result_condition.wait(10)
            if receiver.result_event is None:
                self.fail("Listener did not receive an event")
            assert receiver.result_event.meta_data.create_time <= \
                receiver.result_event.meta_data.send_time
            assert receiver.result_event.meta_data.send_time <= \
                receiver.result_event.meta_data.receive_time
            assert receiver.result_event.meta_data.receive_time <= \
                receiver.result_event.meta_data.deliver_time
            sent_event.meta_data.receive_time = \
                receiver.result_event.meta_data.receive_time
            sent_event.meta_data.deliver_time = \
                receiver.result_event.meta_data.deliver_time
            # HACK: floating point precision leads to an imprecision here,
            # avoid this.
            sent_event.meta_data.send_time = \
                receiver.result_event.meta_data.send_time
            sent_event.meta_data.create_time = \
                receiver.result_event.meta_data.create_time
            assert sent_event == receiver.result_event

        listener.deactivate()
        publisher.deactivate()

    @pytest.mark.timeout(5)
    def test_user_pull_roundtrip(self):
        scope = Scope("/test/it/pull")
        try:
            in_connector = self._get_in_pull_connector(scope, activate=False)
        except NotImplementedError:
            return
        out_connector = self._get_out_connector(scope, activate=False)

        out_configurator = rsb.eventprocessing.OutRouteConfigurator(
            connectors=[out_connector])
        in_configurator = rsb.eventprocessing.InPullRouteConfigurator(
            connectors=[in_connector])

        publisher = create_informer(scope,
                                    data_type=str,
                                    configurator=out_configurator)
        reader = create_reader(scope, configurator=in_configurator)

        data1 = "a string to test"
        sent_event = Event(EventId(uuid.uuid4(), 0))
        sent_event.set_data(data1)
        sent_event.set_data_type(str)
        sent_event.set_scope(scope)
        sent_event.get_meta_data().set_user_info("test", "it")
        sent_event.get_meta_data().set_user_info("test again", "it works?")
        sent_event.get_meta_data().set_user_time("blubb", 234234)
        sent_event.get_meta_data().set_user_time("bla", 3434343.45)
        sent_event.add_cause(EventId(uuid.uuid4(), 1323))
        sent_event.add_cause(EventId(uuid.uuid4(), 42))

        publisher.publish_event(sent_event)

        result_event = reader.read(True)
        assert result_event.meta_data.create_time <= \
            result_event.meta_data.send_time
        assert result_event.meta_data.send_time <= \
            result_event.meta_data.receive_time
        assert result_event.meta_data.receive_time <= \
            result_event.meta_data.deliver_time
        sent_event.meta_data.receive_time = result_event.meta_data.receive_time
        sent_event.meta_data.deliver_time = result_event.meta_data.deliver_time
        assert sent_event == result_event

        reader.deactivate()
        publisher.deactivate()

    @pytest.mark.timeout(5)
    def test_hierarchy_sending(self):

        send_scope = Scope("/this/is/a/test")
        super_scopes = send_scope.super_scopes(True)

        out_connector = self._get_out_connector(send_scope, activate=False)
        out_configurator = rsb.eventprocessing.OutRouteConfigurator(
            connectors=[out_connector])
        informer = create_informer(send_scope,
                                   data_type=str,
                                   configurator=out_configurator)

        # set up listeners on the complete hierarchy
        listeners = []
        receivers = []
        for scope in super_scopes:

            in_connector = self._get_in_push_connector(scope, activate=False)
            in_configurator = rsb.eventprocessing.InPushRouteConfigurator(
                connectors=[in_connector])

            listener = create_listener(scope, configurator=in_configurator)
            listeners.append(listener)

            receiver = SettingReceiver(scope)

            listener.add_handler(receiver)

            receivers.append(receiver)

        data = "a string to test"
        informer.publish_data(data)

        for receiver in receivers:
            with receiver.result_condition:
                while receiver.result_event is None:
                    receiver.result_condition.wait(10)
                if receiver.result_event is None:
                    pytest.fail(
                        "Listener on scope {} did not receive an event".format(
                            receiver.scope))
                assert receiver.result_event.data == data

        for listener in listeners:
            listener.deactivate()
        informer.deactivate()

    def test_send_time_adaption(self):
        scope = Scope("/notGood")
        connector = self._get_out_connector(scope)

        event = Event(EventId(uuid.uuid4(), 0))
        event.scope = scope
        event.data = "".join(
            random.choice(string.ascii_uppercase + string.ascii_lowercase +
                          string.digits) for i in list(range(300502)))
        event.data_type = str
        event.meta_data.sender_id = uuid.uuid4()

        before = time.time()
        connector.handle(event)
        after = time.time()

        assert event.get_meta_data().get_send_time() >= before
        assert event.get_meta_data().get_send_time() <= after

        connector.deactivate()
