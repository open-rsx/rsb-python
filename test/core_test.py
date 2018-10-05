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
import unittest
import uuid
from uuid import uuid4

import rsb
from rsb import (Event,
                 EventId,
                 get_default_participant_config,
                 Informer,
                 MetaData,
                 Participant,
                 ParticipantConfig,
                 QualityOfServiceSpec,
                 Scope,
                 set_default_participant_config)
from rsb.converter import Converter, register_global_converter


class ParticipantConfigTest(unittest.TestCase):

    def test_construction(self):
        ParticipantConfig()

    def test_copy(self):
        transport = ParticipantConfig.Transport('socket',
                                                options={'enabled': '1'})
        config = ParticipantConfig(transports={'socket': transport})
        config.introspection = True

        copied = copy.deepcopy(config)
        copied.introspection = False
        copied.transports[0].enabled = False

        # Assert source object is unmodified.
        self.assertTrue(config.introspection)
        self.assertTrue(config.transports[0].enabled)

    def test_from_file(self):
        config = ParticipantConfig.from_file('test/smoke-test.conf')

        # Check quality of service specs
        self.assertEqual(
            config.get_quality_of_service_spec().get_reliability(),
            QualityOfServiceSpec.Reliability.UNRELIABLE)
        self.assertEqual(
            config.get_quality_of_service_spec().get_ordering(),
            QualityOfServiceSpec.Ordering.UNORDERED)

        self.assertEqual(len(config.get_transports()), 1)
        self.assertEqual(len(config.get_transports(include_disabled=True)), 2)

        # Check introspection
        self.assertTrue(config.introspection)

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
        self.assertEqual(
            config.get_quality_of_service_spec().get_reliability(),
            QualityOfServiceSpec.Reliability.UNRELIABLE)
        self.assertEqual(
            config.get_quality_of_service_spec().get_ordering(),
            QualityOfServiceSpec.Ordering.UNORDERED)

        self.assertEqual(len(config.get_transports()), 1)
        self.assertEqual(len(config.get_transports(include_disabled=True)), 1)

        # Check introspection
        self.assertTrue(config.introspection)

    def test_overwriting_defaults(self):
        defaults = {'transport.spread.enabled': 'yes',
                    'qualityofservice.reliability': 'UNRELIABLE'}
        config = ParticipantConfig.from_dict(defaults)
        self.assertEqual(
            config.get_quality_of_service_spec().get_reliability(),
            QualityOfServiceSpec.Reliability.UNRELIABLE)
        self.assertTrue(config.get_transport('spread').is_enabled())

        os.environ['RSB_QUALITYOFSERVICE_RELIABILITY'] = 'RELIABLE'
        os.environ['RSB_TRANSPORT_SPREAD_ENABLED'] = 'no'
        config = ParticipantConfig.from_environment(defaults)

        # Check overwritten values
        self.assertEqual(
            config.get_quality_of_service_spec().get_reliability(),
            QualityOfServiceSpec.Reliability.RELIABLE)
        self.assertFalse(config.get_transport('spread').is_enabled())

    def test_from_default_source(self):
        # TODO how to test this?
        pass

    def test_mutation(self):
        config = ParticipantConfig()

        config.introspection = True
        self.assertTrue(config.introspection)
        config.set_introspection(False)
        self.assertFalse(config.introspection)


class QualityOfServiceSpecTest(unittest.TestCase):

    def test_construction(self):

        specs = QualityOfServiceSpec()
        self.assertEqual(QualityOfServiceSpec.Ordering.UNORDERED,
                         specs.get_ordering())
        self.assertEqual(QualityOfServiceSpec.Reliability.RELIABLE,
                         specs.get_reliability())

    def test_comparison(self):

        self.assertEqual(
            QualityOfServiceSpec(QualityOfServiceSpec.Ordering.UNORDERED,
                                 QualityOfServiceSpec.Reliability.RELIABLE),
            QualityOfServiceSpec())


class ScopeTest(unittest.TestCase):

    def test_parsing(self):

        root = rsb.Scope("/")
        self.assertEqual(0, len(root.get_components()))

        one_part = rsb.Scope("/test/")
        self.assertEqual(1, len(one_part.get_components()))
        self.assertEqual("test", one_part.get_components()[0])

        many_parts = rsb.Scope("/this/is/a/dumb3/test/")
        self.assertEqual(5, len(many_parts.get_components()))
        self.assertEqual("this", many_parts.get_components()[0])
        self.assertEqual("is", many_parts.get_components()[1])
        self.assertEqual("a", many_parts.get_components()[2])
        self.assertEqual("dumb3", many_parts.get_components()[3])
        self.assertEqual("test", many_parts.get_components()[4])

        # also ensure that the shortcut syntax works
        shortcut = rsb.Scope("/this/is")
        self.assertEqual(2, len(shortcut.get_components()))
        self.assertEqual("this", shortcut.get_components()[0])
        self.assertEqual("is", shortcut.get_components()[1])

        # Non-ASCII characters are not allowed. However, unicode
        # object consisting of acceptable characters are OK.
        Scope('/')
        Scope('/test')
        self.assertRaises(ValueError, Scope, '/br\xc3\xb6tchen')

    def test_parsing_error(self):

        self.assertRaises(ValueError, rsb.Scope, "")
        self.assertRaises(ValueError, rsb.Scope, " ")
        self.assertRaises(ValueError, rsb.Scope, "/with space/does/not/work/")
        self.assertRaises(ValueError, rsb.Scope, "/with/do#3es/not43as/work/")
        self.assertRaises(ValueError, rsb.Scope, "/this//is/not/allowed/")
        self.assertRaises(ValueError, rsb.Scope, "/this/ /is/not/allowed/")

    def test_to_string(self):

        self.assertEqual("/", rsb.Scope("/").to_string())
        self.assertEqual("/foo/", rsb.Scope("/foo/").to_string())
        self.assertEqual("/foo/bar/", rsb.Scope("/foo/bar/").to_string())
        self.assertEqual("/foo/bar/", rsb.Scope("/foo/bar").to_string())

    def test_concat(self):

        self.assertEqual(rsb.Scope("/"),
                         rsb.Scope("/").concat(rsb.Scope("/")))
        self.assertEqual(rsb.Scope("/a/test/"),
                         rsb.Scope("/").concat(rsb.Scope("/a/test/")))
        self.assertEqual(rsb.Scope("/a/test/"),
                         rsb.Scope("/a/test/").concat(rsb.Scope("/")))
        self.assertEqual(rsb.Scope("/a/test/example"),
                         rsb.Scope("/a/test/").concat(rsb.Scope("/example/")))

    def test_comparison(self):

        self.assertTrue(rsb.Scope("/") == rsb.Scope("/"))
        self.assertFalse(rsb.Scope("/") != rsb.Scope("/"))
        self.assertFalse(rsb.Scope("/") == rsb.Scope("/foo/"))
        self.assertTrue(rsb.Scope("/") != rsb.Scope("/foo/"))

        self.assertTrue(rsb.Scope("/a/") < rsb.Scope("/c/"))
        self.assertTrue(rsb.Scope("/a/") <= rsb.Scope("/c/"))
        self.assertTrue(rsb.Scope("/a/") <= rsb.Scope("/a"))
        self.assertFalse(rsb.Scope("/a/") > rsb.Scope("/c/"))
        self.assertTrue(rsb.Scope("/c/") > rsb.Scope("/a/"))
        self.assertTrue(rsb.Scope("/c/") >= rsb.Scope("/a/"))
        self.assertTrue(rsb.Scope("/c/") >= rsb.Scope("/c/"))

    def test_compare_other_type_no_crash(self):
        self.assertFalse(rsb.Scope("/foo") == "test")
        self.assertFalse("test" == rsb.Scope("/foo"))

    def test_hierarchy_comparison(self):

        self.assertTrue(rsb.Scope("/a/").is_sub_scope_of(rsb.Scope("/")))
        self.assertTrue(rsb.Scope("/a/b/c/").is_sub_scope_of(rsb.Scope("/")))
        self.assertTrue(
            rsb.Scope("/a/b/c/").is_sub_scope_of(rsb.Scope("/a/b/")))
        self.assertFalse(
            rsb.Scope("/a/b/c/").is_sub_scope_of(rsb.Scope("/a/b/c/")))
        self.assertFalse(
            rsb.Scope("/a/b/c/").is_sub_scope_of(rsb.Scope("/a/b/c/d/")))
        self.assertFalse(
            rsb.Scope("/a/x/c/").is_sub_scope_of(rsb.Scope("/a/b/")))

        self.assertTrue(rsb.Scope("/").is_super_scope_of(rsb.Scope("/a/")))
        self.assertTrue(rsb.Scope("/").is_super_scope_of(rsb.Scope("/a/b/c/")))
        self.assertTrue(
            rsb.Scope("/a/b/").is_super_scope_of(rsb.Scope("/a/b/c/")))
        self.assertFalse(
            rsb.Scope("/a/b/c/").is_super_scope_of(rsb.Scope("/a/b/c/")))
        self.assertFalse(
            rsb.Scope("/a/b/c/d/").is_super_scope_of(rsb.Scope("/a/b/c/")))
        self.assertFalse(
            rsb.Scope("/b/").is_super_scope_of(rsb.Scope("/a/b/c/")))

    def test_hash(self):

        self.assertEqual(hash(Scope("/")), hash(Scope("/")))
        self.assertNotEqual(hash(Scope("/")), hash(Scope("/foo")))
        self.assertEqual(hash(Scope("/bla/foo")), hash(Scope("/bla/foo/")))

    def test_super_scopes(self):

        self.assertEqual(0, len(rsb.Scope("/").super_scopes()))

        supers = rsb.Scope("/this/is/a/test/").super_scopes()
        self.assertEqual(4, len(supers))
        self.assertEqual(rsb.Scope("/"), supers[0])
        self.assertEqual(rsb.Scope("/this/"), supers[1])
        self.assertEqual(rsb.Scope("/this/is/"), supers[2])
        self.assertEqual(rsb.Scope("/this/is/a/"), supers[3])

        supers = rsb.Scope("/").super_scopes(True)
        self.assertEqual(1, len(supers))
        self.assertEqual(rsb.Scope("/"), supers[0])

        supers = rsb.Scope("/this/is/a/test/").super_scopes(True)
        self.assertEqual(5, len(supers))
        self.assertEqual(rsb.Scope("/"), supers[0])
        self.assertEqual(rsb.Scope("/this/"), supers[1])
        self.assertEqual(rsb.Scope("/this/is/"), supers[2])
        self.assertEqual(rsb.Scope("/this/is/a/"), supers[3])
        self.assertEqual(rsb.Scope("/this/is/a/test/"), supers[4])


class EventIdTest(unittest.TestCase):

    def test_hashing(self):

        id1 = EventId(uuid.uuid4(), 23)
        id2 = EventId(id1.get_participant_id(), 23)
        id3 = EventId(uuid.uuid4(), 32)
        id4 = EventId(id3.get_participant_id(), 33)

        self.assertEqual(hash(id1), hash(id2))
        self.assertNotEqual(hash(id1), hash(id3))
        self.assertNotEqual(hash(id1), hash(id4))
        self.assertNotEqual(hash(id3), hash(id4))

    def test_get_as_uuid(self):

        id1 = EventId(uuid.uuid4(), 23)
        id2 = EventId(id1.participant_id, 23)
        id3 = EventId(id1.participant_id, 24)
        id4 = EventId(uuid.uuid4(), 24)

        self.assertEqual(id1.get_as_uuid(), id2.get_as_uuid())
        self.assertNotEqual(id1.get_as_uuid(), id3.get_as_uuid())
        self.assertNotEqual(id1.get_as_uuid(), id4.get_as_uuid())
        self.assertNotEqual(id3.get_as_uuid(), id4.get_as_uuid())


class EventTest(unittest.TestCase):

    def setUp(self):
        self.e = rsb.Event()

    def test_constructor(self):

        self.assertEqual(None, self.e.get_data())
        self.assertEqual(Scope("/"), self.e.get_scope())

    def test_data(self):

        data = 42
        self.e.data = data
        self.assertEqual(data, self.e.data)

    def test_scope(self):

        scope = Scope("/123/456")
        self.e.scope = scope
        self.assertEqual(scope, self.e.scope)

    def test_data_type(self):
        t = "asdasd"
        self.e.data_type = t
        self.assertEqual(t, self.e.data_type)

    def test_causes(self):

        sid = uuid.uuid4()
        e = Event(EventId(sid, 32))
        self.assertEqual(0, len(e.causes))
        cause = EventId(uuid4(), 546345)
        e.add_cause(cause)
        self.assertEqual(1, len(e.causes))
        self.assertTrue(e.is_cause(cause))
        self.assertTrue(cause in e.causes)
        e.remove_cause(cause)
        self.assertFalse(e.is_cause(cause))
        self.assertEqual(0, len(e.causes))

    def test_comparison(self):

        sid = uuid.uuid4()
        e1 = Event(EventId(sid, 0))
        e2 = Event(EventId(sid, 0))
        e2.get_meta_data().set_create_time(
            e1.get_meta_data().get_create_time())

        e1.meta_data.set_user_time("foo")
        self.assertNotEqual(e1, e2)
        e2.meta_data.set_user_time(
            "foo", e1.get_meta_data().get_user_times()["foo"])
        self.assertEqual(e1, e2)

        cause = EventId(uuid4(), 42)
        e1.add_cause(cause)
        self.assertNotEqual(e1, e2)
        e2.add_cause(cause)
        self.assertEqual(e1, e2)


class FactoryTest(unittest.TestCase):

    def test_default_participant_config(self):
        self.assertTrue(rsb.get_default_participant_config())

    def test_create_listener(self):
        self.assertTrue(rsb.create_listener("/"))

    def test_create_informer(self):
        self.assertTrue(rsb.create_informer("/"))


class MetaDataTest(unittest.TestCase):

    def test_construction(self):

        before = time.time()
        meta = MetaData()
        after = time.time()

        self.assertTrue(meta.get_create_time() is not None)
        self.assertTrue(meta.get_send_time() is None)
        self.assertTrue(meta.get_receive_time() is None)
        self.assertTrue(meta.get_deliver_time() is None)

        self.assertTrue(meta.get_create_time() >= before)
        self.assertTrue(meta.get_create_time() <= after)

    def test_times_auto(self):

        meta = MetaData()

        before = time.time()

        meta.set_create_time(None)
        meta.set_send_time(None)
        meta.set_receive_time(None)
        meta.set_deliver_time(None)

        after = time.time()

        self.assertNotEqual(None, meta.get_create_time())
        self.assertNotEqual(None, meta.get_send_time())
        self.assertNotEqual(None, meta.get_receive_time())
        self.assertNotEqual(None, meta.get_deliver_time())

        self.assertTrue(before <= meta.get_create_time())
        self.assertTrue(before <= meta.get_send_time())
        self.assertTrue(before <= meta.get_receive_time())
        self.assertTrue(before <= meta.get_deliver_time())

        self.assertTrue(after >= meta.get_create_time())
        self.assertTrue(after >= meta.get_send_time())
        self.assertTrue(after >= meta.get_receive_time())
        self.assertTrue(after >= meta.get_deliver_time())

    def test_user_times(self):

        meta = MetaData()

        before = time.time()
        meta.set_user_time("foo")
        after = time.time()

        self.assertNotEqual(None, meta.user_times["foo"])
        self.assertTrue(meta.user_times["foo"] >= before)
        self.assertTrue(meta.user_times["foo"] <= after)

    def test_comparison(self):

        meta1 = MetaData()
        meta2 = MetaData()
        meta2.set_create_time(meta1.get_create_time())
        self.assertEqual(meta1, meta2)

        meta1.set_create_time(213123)
        self.assertNotEqual(meta1, meta2)
        meta2.set_create_time(meta1.get_create_time())
        self.assertEqual(meta1, meta2)

        meta1.set_send_time()
        self.assertNotEqual(meta1, meta2)
        meta2.set_send_time(meta1.get_send_time())
        self.assertEqual(meta1, meta2)

        meta1.set_receive_time()
        self.assertNotEqual(meta1, meta2)
        meta2.set_receive_time(meta1.get_receive_time())
        self.assertEqual(meta1, meta2)

        meta1.set_deliver_time()
        self.assertNotEqual(meta1, meta2)
        meta2.set_deliver_time(meta1.get_deliver_time())
        self.assertEqual(meta1, meta2)

        meta1.set_user_time("foo")
        self.assertNotEqual(meta1, meta2)
        meta2.set_user_time("foo", meta1.get_user_times()["foo"])
        self.assertEqual(meta1, meta2)

        meta1.set_user_info("foox", "bla")
        self.assertNotEqual(meta1, meta2)
        meta2.set_user_info("foox", meta1.get_user_infos()["foox"])
        self.assertEqual(meta1, meta2)


class InformerTest(unittest.TestCase):

    def setUp(self):
        self.default_scope = Scope("/a/test")
        self.informer = Informer(self.default_scope,
                                 rsb.get_default_participant_config(),
                                 data_type=str)

    def tear_down(self):
        self.informer.deactivate()

    def test_send_event_wrong_scope(self):
        # Error: unrelated scope
        e = Event(scope=Scope("/blubb"), data='foo',
                  data_type=self.informer.data_type)
        self.assertRaises(ValueError, self.informer.publish_event, e)

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
        self.assertRaises(ValueError, self.informer.publish_event, e)

        # Wrong type
        self.assertRaises(ValueError, self.informer.publish_data, 5.0)

        # OK
        self.informer.publish_data('bla')


class IntegrationTest(unittest.TestCase):

    def setUp(self):
        self._previous_config = get_default_participant_config()
        set_default_participant_config(
            ParticipantConfig.from_file('test/with-socket.conf'))

    def tear_down(self):
        set_default_participant_config(self._previous_config)

    def test_lazy_converter_registration(self):
        """
        Tests lazy converter registration.

        Test that converters can be added to the global converter map without
        requiring a completely new instance of the default participant config.
        """

        class FooType(object):
            """Dummy data type for the test."""

        class FooTypeConverter(Converter):

            def __init__(self):
                Converter.__init__(self, bytes, FooType, "footype")

            def serialize(self, inp):
                return bytes(), self.wire_schema

            def deserialize(self, inp, wire_schema):
                return FooType()

        register_global_converter(FooTypeConverter())

        config = get_default_participant_config()
        # this will raise an exception if the converter is not available.
        # This assumes that socket transport is enabled as the only transport
        self.assertTrue(
            isinstance(
                Participant.get_connectors(
                    'out', config)[0].get_converter_for_data_type(FooType),
                FooTypeConverter))


class ContextManagerTest(unittest.TestCase):

    def setUp(self):
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
                self.assertEqual(data, self.received_data)

    def test_rpc_roundtrip(self):

        with rsb.create_server(self.scope) as server, \
                rsb.create_remote_server(self.scope) as client:

            method_name = 'test'
            data = 'bla'

            server.add_method(method_name, lambda x: x, str, str)
            self.assertEqual(data, client.test(data))


class HookTest(unittest.TestCase):

    def setUp(self):
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

    def tear_down(self):
        rsb.participant_creation_hook.remove_handler(self.creation_handler)
        rsb.participant_destruction_hook.remove_handler(
            self.destruction_handler)

    def test_informer(self):
        participant = None
        with rsb.create_informer('/') as informer:
            participant = informer
            self.assertEqual(self.creation_calls, [(participant, None)])
        self.assertEqual(self.destruction_calls, [participant])

    def test_listener(self):
        participant = None
        with rsb.create_listener('/') as listener:
            participant = listener
            self.assertEqual(self.creation_calls, [(participant, None)])
        self.assertEqual(self.destruction_calls, [participant])

    def test_local_server(self):
        server = None
        method = None
        with rsb.create_local_server('/') as participant:
            server = participant
            self.assertEqual(self.creation_calls, [(server, None)])

            method = server.add_method('echo', lambda x: x)
            self.assertTrue((method, server) in self.creation_calls)

        self.assertTrue(server in self.destruction_calls)
        self.assertTrue(method in self.destruction_calls)

    def test_remote_server(self):
        server = None
        method = None
        with rsb.create_remote_server('/') as participant:
            server = participant
            self.assertEqual(self.creation_calls, [(server, None)])

            method = server.echo
            self.assertTrue((method, server) in self.creation_calls)

        self.assertTrue(server in self.destruction_calls)
        self.assertTrue(method in self.destruction_calls)
