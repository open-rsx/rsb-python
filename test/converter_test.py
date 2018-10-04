# ============================================================
#
# Copyright (C) 2011-2016 Jan Moringen
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
import re

import rsb.converter
from rsb.converter import Converter, NoneConverter, StringConverter, \
    ConverterMap, UnambiguousConverterMap, PredicateConverterList, \
    ScopeConverter, EventsByScopeMapConverter
from rsb import Scope, Event, EventId
from uuid import uuid4
from nose.tools import assert_equals


class ConflictingStringConverter(Converter):
    def __init__(self):
        Converter.__init__(self, wire_type=bytes,
                           wire_schema="utf-8-string", data_type=float)

    def serialize(self, input):
        return str(input)

    def deserialize(self, input, wire_schema):
        return str(input)


class ConverterMapTest(unittest.TestCase):
    def test_add_converter(self):
        map = ConverterMap(str)
        map.add_converter(StringConverter())
        map.add_converter(ConflictingStringConverter())
        self.assertRaises(Exception, map.add_converter, StringConverter())
        map.add_converter(StringConverter(), replace_existing=True)


class UnambiguousConverterMapTest(unittest.TestCase):
    def test_add_converter(self):
        map = UnambiguousConverterMap(str)
        map.add_converter(StringConverter())
        self.assertRaises(Exception, map.add_converter,
                          ConflictingStringConverter())
        self.assertRaises(Exception, map.add_converter,
                          ConflictingStringConverter(), True)
        map.add_converter(StringConverter(), replace_existing=True)


class PredicateConverterListTest(unittest.TestCase):
    def assert_is(self, a, b):
        self.assertTrue(a is b)

    def test_add_converter(self):
        list = PredicateConverterList(str)
        list.add_converter(StringConverter())
        list.add_converter(StringConverter(),
                           wire_schema_predicate=lambda wire_schema: True)
        list.add_converter(StringConverter(),
                           data_type_predicate=lambda data_type: True)

    def test_get_converter(self):
        v1 = StringConverter()
        v2 = StringConverter()

        always_true = PredicateConverterList(str)
        always_true.add_converter(v1,
                                  wire_schema_predicate=lambda wire_schema: True,
                                  data_type_predicate=lambda data_type: True)
        self.assert_is(always_true.get_converter_for_wire_schema(""), v1)
        self.assert_is(always_true.get_converter_for_wire_schema("bla"), v1)

        regex = PredicateConverterList(str)
        regex.add_converter(
            v1,
            wire_schema_predicate=lambda wire_schema:
                re.match(".*foo.*", wire_schema),
            data_type_predicate=lambda data_type:
                re.match(".*foo.*", data_type))
        self.assertRaises(KeyError, regex.get_converter_for_wire_schema, "")
        self.assertRaises(KeyError, regex.get_converter_for_wire_schema, "bla")
        self.assert_is(regex.get_converter_for_wire_schema("foo"), v1)
        self.assert_is(regex.get_converter_for_wire_schema("foobar"), v1)
        self.assertRaises(KeyError, regex.get_converter_for_data_type, "")
        self.assertRaises(KeyError, regex.get_converter_for_data_type, "bla")
        self.assert_is(regex.get_converter_for_data_type("foo"), v1)
        self.assert_is(regex.get_converter_for_data_type("foobar"), v1)

        mixed = PredicateConverterList(str)
        mixed.add_converter(
            v1,
            wire_schema_predicate=lambda wire_schema:
                re.match(".*foo.*", wire_schema),
            data_type_predicate=lambda data_type:
                re.match(".*foo.*", data_type))
        mixed.add_converter(v2,
                            wire_schema_predicate=lambda wire_schema: True,
                            data_type_predicate=lambda data_type: True)
        self.assert_is(mixed.get_converter_for_wire_schema(""), v2)
        self.assert_is(mixed.get_converter_for_wire_schema("bla"), v2)
        self.assert_is(mixed.get_converter_for_wire_schema("foo"), v1)
        self.assert_is(mixed.get_converter_for_wire_schema("foobar"), v1)
        self.assert_is(mixed.get_converter_for_data_type(""), v2)
        self.assert_is(mixed.get_converter_for_data_type("bla"), v2)
        self.assert_is(mixed.get_converter_for_data_type("foo"), v1)
        self.assert_is(mixed.get_converter_for_data_type("foobar"), v1)


class NoneConverterTest(unittest.TestCase):
    def test_roundtrip(self):
        converter = NoneConverter()
        self.assertEqual(None,
                         converter.deserialize(*converter.serialize(None)))


class StringConverterTest(unittest.TestCase):

    def test_roundtrip_utf8(self):
        converter = StringConverter()
        orig = "asd" + chr(270) + chr(40928)
        self.assertEqual(orig,
                         converter.deserialize(*converter.serialize(orig)))
        orig = "i am a normal string"
        self.assertEqual(orig,
                         converter.deserialize(*converter.serialize(orig)))

    def test_roundtrip_ascii(self):
        converter = StringConverter(wire_schema="ascii-string",
                                    encoding="ascii")
        orig = "foooo"
        self.assertEqual(orig,
                         converter.deserialize(*converter.serialize(orig)))

    def test_charset_errors(self):
        ascii_converter = StringConverter(wire_schema="ascii-string",
                                          encoding="ascii")
        self.assertRaises(UnicodeEncodeError,
                          ascii_converter.serialize, "test" + chr(266))
        self.assertRaises(UnicodeDecodeError, ascii_converter.deserialize,
                          bytes(list(range(133))), 'ascii-string')


class ScopeConverterTest(unittest.TestCase):

    def test_round_trip(self):
        converter = ScopeConverter()

        root = Scope('/foo/bar')
        self.assertEqual(root,
                         converter.deserialize(*converter.serialize(root)))

        some_scope = Scope('/foo/bar')
        self.assertEqual(some_scope,
                         converter.deserialize(*converter.serialize(some_scope)))


class EventsByScopeMapConverterTest(unittest.TestCase):

    def test_empty_roundtrip(self):

        data = {}
        converter = EventsByScopeMapConverter()
        self.assertEqual(data,
                         converter.deserialize(*converter.serialize(data)))

    def test_roundtrip(self):
        self.max_diff = None

        data = {}
        scope1 = Scope("/a/test")
        event1 = Event(id=EventId(uuid4(), 32), scope=scope1,
                       method="foo", data=42, type=int,
                       user_times={"foo": 1231234.0})
        event1.meta_data.set_send_time()
        event1.meta_data.set_receive_time()
        event2 = Event(id=EventId(uuid4(), 1001), scope=scope1,
                       method="fooasdas", data=422, type=int,
                       user_times={"bar": 1234.05})
        event2.meta_data.set_send_time()
        event2.meta_data.set_receive_time()
        data[scope1] = [event1, event2]

        converter = EventsByScopeMapConverter()
        roundtripped = converter.deserialize(*converter.serialize(data))

        self.assertEqual(1, len(roundtripped))
        self.assertTrue(scope1 in roundtripped)
        self.assertEqual(len(data[scope1]), len(roundtripped[scope1]))

        for orig, converted in zip(data[scope1], roundtripped[scope1]):

            self.assertEqual(orig.id, converted.id)
            self.assertEqual(orig.scope, converted.scope)
            # This test currently does not work correctly without a patch for
            # the converter selection for fundamental types
            # self.assertEqual(orig.type, converted.type)
            self.assertEqual(orig.data, converted.data)
            self.assertAlmostEqual(orig.meta_data.create_time,
                                   converted.meta_data.create_time,
                                   places=4)
            self.assertEqual(orig.causes, converted.causes)


def check_structure_based_rountrip(converter_name, values):
    converter = rsb.converter.__dict__[converter_name]()
    for value in values:
        assert_equals(value,
                      converter.deserialize(*converter.serialize(value)))


def test_structure_base_converters():
    for converter_name, values in [
            ('DoubleConverter', [0.0, -1.0, 1.0]),
            ('FloatConverter', [0.0, -1.0, 1.0]),
            ('Int32Converter', [0, -1, 1, -24378, ((1 << 31) - 1)]),
            ('Int64Converter', [0, -1, 1, -24378, ((1 << 63) - 1)]),
            ('Uint32Converter', [0, 1, 24378, ((1 << 32) - 1)]),
            ('Uint64Converter', [0, 1, 24378, ((1 << 32) - 1)]),
            ('BoolConverter', [True, False])]:
        yield check_structure_based_rountrip, converter_name, values
