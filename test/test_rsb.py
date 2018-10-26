# ============================================================
#
# Copyright (C) 2010 by Johannes Wienke
# Copyright (C) 2014 Jan Moringen
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

import copy
import os
from threading import Condition
import time
import uuid
from uuid import uuid4

import pytest

import rsb
from rsb import (Event,
                 EventId,
                 get_default_participant_config,
                 Informer,
                 MetaData,
                 Participant,
                 ParticipantConfig,
                 QualityOfServiceSpec,
                 Scope)
from rsb.converter import Converter, register_global_converter


class TestParticipantConfig:

    def test_construction(self):
        ParticipantConfig()

    def test_copy(self):
        transport = ParticipantConfig.Transport('socket',
                                                options={'enabled': '1'})
        config = ParticipantConfig(transports={'socket': transport})
        config.introspection = True

        copied = copy.deepcopy(config)
        copied.introspection = False
        copied.enabled_transports[0].enabled = False

        # Assert source object is unmodified.
        assert config.introspection
        assert config.enabled_transports[0].enabled

    def test_from_file(self):
        config = ParticipantConfig.from_file('test/smoke-test.conf')

        # Check quality of service specs
        assert config.quality_of_service_spec.reliability == \
            QualityOfServiceSpec.Reliability.UNRELIABLE
        assert config.quality_of_service_spec.ordering == \
            QualityOfServiceSpec.Ordering.UNORDERED

        assert len(config.enabled_transports) == 1
        assert len(config.all_transports) == 2

        # Check introspection
        assert config.introspection

    def test_from_environment(self):
        # Clear RSB-specific variables from environment
        os.environ = {key: value
                      for (key, value) in list(os.environ.items())
                      if 'RSB' not in key}

        os.environ['RSB_QUALITYOFSERVICE_RELIABILITY'] = 'UNRELIABLE'
        os.environ['RSB_QUALITYOFSERVICE_ORDERED'] = 'UNORDERED'

        os.environ['RSB_TRANSPORT_INPROCESS_ENABLED'] = '1'

        os.environ['RSB_INTROSPECTION_ENABLED'] = '1'

        config = ParticipantConfig.from_environment()

        # Check quality of service specs
        assert config.quality_of_service_spec.reliability == \
            QualityOfServiceSpec.Reliability.UNRELIABLE
        assert config.quality_of_service_spec.ordering == \
            QualityOfServiceSpec.Ordering.UNORDERED

        assert len(config.enabled_transports) == 1
        assert len(config.all_transports) == 1

        # Check introspection
        assert config.introspection

    def test_overwriting_defaults(self):
        defaults = {'transport.spread.enabled': 'yes',
                    'qualityofservice.reliability': 'UNRELIABLE'}
        config = ParticipantConfig.from_dict(defaults)
        assert config.quality_of_service_spec.reliability == \
            QualityOfServiceSpec.Reliability.UNRELIABLE
        assert config.get_transport('spread').enabled

        os.environ['RSB_QUALITYOFSERVICE_RELIABILITY'] = 'RELIABLE'
        os.environ['RSB_TRANSPORT_SPREAD_ENABLED'] = 'no'
        config = ParticipantConfig.from_environment(defaults)

        # Check overwritten values
        assert config.quality_of_service_spec.reliability == \
            QualityOfServiceSpec.Reliability.RELIABLE
        assert not config.get_transport('spread').enabled

    def test_from_default_source(self):
        # TODO how to test this?
        pass

    def test_mutation(self):
        config = ParticipantConfig()

        config.introspection = True
        assert config.introspection
        config.introspection = False
        assert not config.introspection


class TestQualityOfServiceSpec:

    def test_construction(self):

        specs = QualityOfServiceSpec()
        assert QualityOfServiceSpec.Ordering.UNORDERED == specs.ordering
        assert QualityOfServiceSpec.Reliability.RELIABLE == \
            specs.reliability

    def test_comparison(self):

        assert QualityOfServiceSpec(
            QualityOfServiceSpec.Ordering.UNORDERED,
            QualityOfServiceSpec.Reliability.RELIABLE) == \
            QualityOfServiceSpec()


class TestScope:

    @pytest.mark.parametrize('str_repr,components', [
        ('/', []),
        ('/test/', ['test']),
        ('/this/is/a/dumb3/test/', ['this', 'is', 'a', 'dumb3', 'test']),
        ('/this/is', ['this', 'is']),  # shortcut syntax without slash
    ])
    def test_parsing(self, str_repr, components):
        scope = rsb.Scope(str_repr)
        assert scope.components == components

        # Non-ASCII characters are not allowed. However, unicode
        # object consisting of acceptable characters are OK.
        with pytest.raises(ValueError):
            Scope('/br\xc3\xb6tchen')

    @pytest.mark.parametrize('str_repr', [
        '',
        ' ',
        '/with space/does/not/work/',
        '/with/do#3es/not43as/work/',
        '/this//is/not/allowed/',
        '/this/ /is/not/allowed/',
        '/br\xc3\xb6tchen',
    ])
    def test_parsing_error(self, str_repr):
        with pytest.raises(ValueError):
            Scope(str_repr)

    @pytest.mark.parametrize('str_input,expected', [
        ('/', '/'),
        ('/foo/', '/foo/'),
        ('/foo/bar/', '/foo/bar/'),
        ('/foo/bar', '/foo/bar/'),  # shortcut syntax
    ])
    def test_to_string(self, str_input, expected):
        assert rsb.Scope(str_input).to_string() == expected

    def test_concat(self):

        assert rsb.Scope("/") == rsb.Scope("/").concat(rsb.Scope("/"))
        assert rsb.Scope("/a/test/") == rsb.Scope("/").concat(
            rsb.Scope("/a/test/"))
        assert rsb.Scope("/a/test/") == rsb.Scope("/a/test/").concat(
            rsb.Scope("/"))
        assert rsb.Scope("/a/test/example") == rsb.Scope("/a/test/").concat(
            rsb.Scope("/example/"))

    def test_comparison(self):

        assert rsb.Scope("/") == rsb.Scope("/")
        assert not (rsb.Scope("/") != rsb.Scope("/"))
        assert not (rsb.Scope("/") == rsb.Scope("/foo/"))
        assert rsb.Scope("/") != rsb.Scope("/foo/")

        assert rsb.Scope("/a/") < rsb.Scope("/c/")
        assert rsb.Scope("/a/") <= rsb.Scope("/c/")
        assert rsb.Scope("/a/") <= rsb.Scope("/a")
        assert not (rsb.Scope("/a/") > rsb.Scope("/c/"))
        assert rsb.Scope("/c/") > rsb.Scope("/a/")
        assert rsb.Scope("/c/") >= rsb.Scope("/a/")
        assert rsb.Scope("/c/") >= rsb.Scope("/c/")

    def test_compare_other_type_no_crash(self):
        assert not (rsb.Scope("/foo") == "test")
        assert not ("test" == rsb.Scope("/foo"))

    def test_hierarchy_comparison(self):

        assert rsb.Scope("/a/").is_sub_scope_of(rsb.Scope("/"))
        assert rsb.Scope("/a/b/c/").is_sub_scope_of(rsb.Scope("/"))
        assert rsb.Scope("/a/b/c/").is_sub_scope_of(rsb.Scope("/a/b/"))
        assert not rsb.Scope("/a/b/c/").is_sub_scope_of(rsb.Scope("/a/b/c/"))
        assert not rsb.Scope("/a/b/c/").is_sub_scope_of(rsb.Scope("/a/b/c/d/"))
        assert not rsb.Scope("/a/x/c/").is_sub_scope_of(rsb.Scope("/a/b/"))

        assert rsb.Scope("/").is_super_scope_of(rsb.Scope("/a/"))
        assert rsb.Scope("/").is_super_scope_of(rsb.Scope("/a/b/c/"))
        assert rsb.Scope("/a/b/").is_super_scope_of(rsb.Scope("/a/b/c/"))
        assert not rsb.Scope("/a/b/c/").is_super_scope_of(rsb.Scope("/a/b/c/"))
        assert not rsb.Scope("/a/b/c/d/").is_super_scope_of(
            rsb.Scope("/a/b/c/"))
        assert not rsb.Scope("/b/").is_super_scope_of(rsb.Scope("/a/b/c/"))

    def test_hash(self):

        assert hash(Scope("/")) == hash(Scope("/"))
        assert hash(Scope("/")) != hash(Scope("/foo"))
        assert hash(Scope("/bla/foo")) == hash(Scope("/bla/foo/"))

    @pytest.mark.parametrize('scope,supers', [
        (rsb.Scope('/'),
         [rsb.Scope('/')]),
        (rsb.Scope('/this/is/a/test/'),
         [rsb.Scope('/'),
          rsb.Scope('/this'),
          rsb.Scope('/this/is'),
          rsb.Scope('/this/is/a'),
          rsb.Scope('/this/is/a/test')]),
    ])
    def test_super_scopes(self, scope, supers):
        assert scope.super_scopes() == supers[:-1]
        assert scope.super_scopes(True) == supers


class TestEventId:

    def test_hashing(self):

        id1 = EventId(uuid.uuid4(), 23)
        id2 = EventId(id1.participant_id, 23)
        id3 = EventId(uuid.uuid4(), 32)
        id4 = EventId(id3.participant_id, 33)

        assert hash(id1) == hash(id2)
        assert hash(id1) != hash(id3)
        assert hash(id1) != hash(id4)
        assert hash(id3) != hash(id4)

    def test_get_as_uuid(self):

        id1 = EventId(uuid.uuid4(), 23)
        id2 = EventId(id1.participant_id, 23)
        id3 = EventId(id1.participant_id, 24)
        id4 = EventId(uuid.uuid4(), 24)

        assert id1.get_as_uuid() == id2.get_as_uuid()
        assert id1.get_as_uuid() != id3.get_as_uuid()
        assert id1.get_as_uuid() != id4.get_as_uuid()
        assert id3.get_as_uuid() != id4.get_as_uuid()


class TestEvent:

    def test_constructor(self):
        e = Event()
        assert e.data is None
        assert Scope("/") == e.scope

    def test_data(self):
        e = Event()
        data = 42
        e.data = data
        assert data == e.data

    def test_scope(self):
        e = Event()
        scope = Scope("/123/456")
        e.scope = scope
        assert scope == e.scope

    def test_data_type(self):
        e = Event()
        t = "asdasd"
        e.data_type = t
        assert t == e.data_type

    def test_causes(self):

        sid = uuid.uuid4()
        e = Event(EventId(sid, 32))
        assert len(e.causes) == 0
        cause = EventId(uuid4(), 546345)
        e.add_cause(cause)
        assert len(e.causes) == 1
        assert e.is_cause(cause)
        assert cause in e.causes
        e.remove_cause(cause)
        assert not e.is_cause(cause)
        assert len(e.causes) == 0

    def test_comparison(self):

        sid = uuid.uuid4()
        e1 = Event(EventId(sid, 0))
        e2 = Event(EventId(sid, 0))
        e2.meta_data.set_create_time(
            e1.meta_data.create_time)

        e1.meta_data.set_user_time("foo")
        assert e1 != e2
        e2.meta_data.set_user_time(
            "foo", e1.meta_data.user_times["foo"])
        assert e1 == e2

        cause = EventId(uuid4(), 42)
        e1.add_cause(cause)
        assert e1 != e2
        e2.add_cause(cause)
        assert e1 == e2


class TestFactory:

    def test_default_participant_config(self):
        assert rsb.get_default_participant_config() is not None

    def test_create_listener(self):
        assert rsb.create_listener("/") is not None

    def test_create_informer(self):
        assert rsb.create_informer("/") is not None


class TestMetaData:

    def test_construction(self):

        before = time.time()
        meta = MetaData()
        after = time.time()

        assert meta.create_time is not None
        assert meta.send_time is None
        assert meta.receive_time is None
        assert meta.deliver_time is None

        assert meta.create_time >= before
        assert meta.create_time <= after

    def test_times_auto(self):

        meta = MetaData()

        before = time.time()

        meta.set_create_time(None)
        meta.set_send_time(None)
        meta.set_receive_time(None)
        meta.set_deliver_time(None)

        after = time.time()

        assert meta.create_time is not None
        assert meta.send_time is not None
        assert meta.receive_time is not None
        assert meta.deliver_time is not None

        assert before <= meta.create_time
        assert before <= meta.send_time
        assert before <= meta.receive_time
        assert before <= meta.deliver_time

        assert after >= meta.create_time
        assert after >= meta.send_time
        assert after >= meta.receive_time
        assert after >= meta.deliver_time

    def test_user_times(self):

        meta = MetaData()

        before = time.time()
        meta.set_user_time("foo")
        after = time.time()

        assert meta.user_times["foo"] is not None
        assert meta.user_times["foo"] >= before
        assert meta.user_times["foo"] <= after

    def test_comparison(self):

        meta1 = MetaData()
        meta2 = MetaData()
        meta2.set_create_time(meta1.create_time)
        assert meta1 == meta2

        meta1.set_create_time(213123)
        assert meta1 != meta2
        meta2.set_create_time(meta1.create_time)
        assert meta1 == meta2

        meta1.set_send_time()
        assert meta1 != meta2
        meta2.set_send_time(meta1.send_time)
        assert meta1 == meta2

        meta1.set_receive_time()
        assert meta1 != meta2
        meta2.set_receive_time(meta1.receive_time)
        assert meta1 == meta2

        meta1.set_deliver_time()
        assert meta1 != meta2
        meta2.set_deliver_time(meta1.deliver_time)
        assert meta1 == meta2

        meta1.set_user_time("foo")
        assert meta1 != meta2
        meta2.set_user_time("foo", meta1.user_times["foo"])
        assert meta1 == meta2

        meta1.set_user_info("foox", "bla")
        assert meta1 != meta2
        meta2.set_user_info("foox", meta1.user_infos["foox"])
        assert meta1 == meta2


class TestInformer:

    @pytest.fixture(autouse=True)
    def set_up(self):
        self.default_scope = Scope("/a/test")
        self.informer = Informer(self.default_scope,
                                 rsb.get_default_participant_config(),
                                 data_type=str)

        yield

        self.informer.deactivate()

    def test_send_event_wrong_scope(self):
        # Error: unrelated scope
        e = Event(scope=Scope("/blubb"), data='foo',
                  data_type=self.informer.data_type)
        with pytest.raises(ValueError):
            self.informer.publish_event(e)

        # OK: identical scope
        e = Event(scope=self.default_scope,
                  data='foo', data_type=self.informer.data_type)
        self.informer.publish_event(e)

        # OK: sub-scope
        e = Event(scope=self.default_scope.concat(Scope('/sub')),
                  data='foo',
                  data_type=self.informer.data_type)
        self.informer.publish_event(e)

    def test_send_event_wrong_type(self):
        # Wrong type
        e = Event(scope=self.default_scope, data=5)
        with pytest.raises(ValueError):
            self.informer.publish_event(e)

        # Wrong type
        with pytest.raises(ValueError):
            self.informer.publish_data(5.0)

        # OK
        self.informer.publish_data('bla')


class TetsIntegration:

    @pytest.mark.usefixture('rsb_config_socket')
    def test_lazy_converter_registration(self):
        """
        Tests lazy converter registration.

        Test that converters can be added to the global converter map without
        requiring a completely new instance of the default participant config.
        """

        class FooType:
            """Dummy data type for the test."""

        class FooTypeConverter(Converter):

            def __init__(self):
                super().__init__(bytes, FooType, "footype")

            def serialize(self, inp):
                return bytes(), self.wire_schema

            def deserialize(self, inp, wire_schema):
                return FooType()

        register_global_converter(FooTypeConverter())

        config = get_default_participant_config()
        # this will raise an exception if the converter is not available.
        # This assumes that socket transport is enabled as the only transport
        assert isinstance(
            Participant.get_connectors(
                'out', config)[0].get_converter_for_data_type(FooType),
            FooTypeConverter)


class TestContextManager:

    @pytest.fixture(autouse=True)
    def set_up(self):
        self.scope = rsb.Scope('/one/test')
        self.received_condition = Condition()
        self.received_data = None

    def test_informer_listener_roundtrip(self):

        with rsb.create_informer(self.scope, data_type=str) as informer, \
                rsb.create_listener(self.scope) as listener:
            def set_received(event):
                with self.received_condition:
                    self.received_data = event.data
                    self.received_condition.notifyAll()
            listener.add_handler(set_received)
            data = 'our little test'
            informer.publish_data(data)
            start = time.time()
            with self.received_condition:
                while self.received_data is None:
                    self.received_condition.wait(1)
                    if time.time() > start + 10:
                        break
                assert data == self.received_data

    def test_rpc_roundtrip(self):

        with rsb.create_local_server(self.scope) as server, \
                rsb.create_remote_server(self.scope) as client:

            method_name = 'test'
            data = 'bla'

            server.add_method(method_name, lambda x: x, str, str)
            assert data == client.test(data)


class TestHook:

    @pytest.fixture(autouse=True)
    def set_up(self):
        self.creation_calls = []

        def handle_creation(participant, parent=None):
            self.creation_calls.append((participant, parent))

        self.creation_handler = handle_creation
        rsb.participant_creation_hook.add_handler(self.creation_handler)

        self.destruction_calls = []

        def handle_destruction(participant):
            self.destruction_calls.append(participant)

        self.destruction_handler = handle_destruction
        rsb.participant_destruction_hook.add_handler(self.destruction_handler)

        yield

        rsb.participant_creation_hook.remove_handler(self.creation_handler)
        rsb.participant_destruction_hook.remove_handler(
            self.destruction_handler)

    def test_informer(self):
        participant = None
        with rsb.create_informer('/') as informer:
            participant = informer
            assert self.creation_calls == [(participant, None)]
        assert self.destruction_calls == [participant]

    def test_listener(self):
        participant = None
        with rsb.create_listener('/') as listener:
            participant = listener
            assert self.creation_calls == [(participant, None)]
        assert self.destruction_calls == [participant]

    def test_local_server(self):
        server = None
        method = None
        with rsb.create_local_server('/') as participant:
            server = participant
            assert self.creation_calls == [(server, None)]

            method = server.add_method('echo', lambda x: x)
            assert (method, server) in self.creation_calls

        assert server in self.destruction_calls
        assert method in self.destruction_calls

    def test_remote_server(self):
        server = None
        method = None
        with rsb.create_remote_server('/') as participant:
            server = participant
            assert self.creation_calls == [(server, None)]

            method = server.echo
            assert (method, server) in self.creation_calls

        assert server in self.destruction_calls
        assert method in self.destruction_calls
