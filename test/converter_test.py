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
        Converter.__init__(self, wireType=bytes,
                           wireSchema="utf-8-string", dataType=float)

    def serialize(self, input):
        return str(input)

    def deserialize(self, input, wireSchema):
        return str(input)


class ConverterMapTest(unittest.TestCase):
    def testAddConverter(self):
        map = ConverterMap(str)
        map.addConverter(StringConverter())
        map.addConverter(ConflictingStringConverter())
        self.assertRaises(Exception, map.addConverter, StringConverter())
        map.addConverter(StringConverter(), replaceExisting=True)


class UnambiguousConverterMapTest(unittest.TestCase):
    def testAddConverter(self):
        map = UnambiguousConverterMap(str)
        map.addConverter(StringConverter())
        self.assertRaises(Exception, map.addConverter,
                          ConflictingStringConverter())
        self.assertRaises(Exception, map.addConverter,
                          ConflictingStringConverter(), True)
        map.addConverter(StringConverter(), replaceExisting=True)


class PredicateConverterListTest(unittest.TestCase):
    def assertIs(self, a, b):
        self.assertTrue(a is b)

    def testAddConverter(self):
        list = PredicateConverterList(str)
        list.addConverter(StringConverter())
        list.addConverter(StringConverter(),
                          wireSchemaPredicate=lambda wireSchema: True)
        list.addConverter(StringConverter(),
                          dataTypePredicate=lambda dataType: True)

    def testGetConverter(self):
        v1 = StringConverter()
        v2 = StringConverter()

        alwaysTrue = PredicateConverterList(str)
        alwaysTrue.addConverter(v1,
                                wireSchemaPredicate=lambda wireSchema: True,
                                dataTypePredicate=lambda dataType: True)
        self.assertIs(alwaysTrue.getConverterForWireSchema(""), v1)
        self.assertIs(alwaysTrue.getConverterForWireSchema("bla"), v1)

        regex = PredicateConverterList(str)
        regex.addConverter(
            v1,
            wireSchemaPredicate=lambda wireSchema:
                re.match(".*foo.*", wireSchema),
            dataTypePredicate=lambda dataType:
                re.match(".*foo.*", dataType))
        self.assertRaises(KeyError, regex.getConverterForWireSchema, "")
        self.assertRaises(KeyError, regex.getConverterForWireSchema, "bla")
        self.assertIs(regex.getConverterForWireSchema("foo"), v1)
        self.assertIs(regex.getConverterForWireSchema("foobar"), v1)
        self.assertRaises(KeyError, regex.getConverterForDataType, "")
        self.assertRaises(KeyError, regex.getConverterForDataType, "bla")
        self.assertIs(regex.getConverterForDataType("foo"), v1)
        self.assertIs(regex.getConverterForDataType("foobar"), v1)

        mixed = PredicateConverterList(str)
        mixed.addConverter(
            v1,
            wireSchemaPredicate=lambda wireSchema:
                re.match(".*foo.*", wireSchema),
            dataTypePredicate=lambda dataType:
                re.match(".*foo.*", dataType))
        mixed.addConverter(v2,
                           wireSchemaPredicate=lambda wireSchema: True,
                           dataTypePredicate=lambda dataType: True)
        self.assertIs(mixed.getConverterForWireSchema(""), v2)
        self.assertIs(mixed.getConverterForWireSchema("bla"), v2)
        self.assertIs(mixed.getConverterForWireSchema("foo"), v1)
        self.assertIs(mixed.getConverterForWireSchema("foobar"), v1)
        self.assertIs(mixed.getConverterForDataType(""), v2)
        self.assertIs(mixed.getConverterForDataType("bla"), v2)
        self.assertIs(mixed.getConverterForDataType("foo"), v1)
        self.assertIs(mixed.getConverterForDataType("foobar"), v1)


class NoneConverterTest(unittest.TestCase):
    def testRoundtrip(self):
        converter = NoneConverter()
        self.assertEqual(None,
                          converter.deserialize(*converter.serialize(None)))


class StringConverterTest(unittest.TestCase):

    def testRoundtripUtf8(self):
        converter = StringConverter()
        orig = "asd" + chr(270) + chr(40928)
        self.assertEqual(orig,
                          converter.deserialize(*converter.serialize(orig)))
        orig = "i am a normal string"
        self.assertEqual(orig,
                          converter.deserialize(*converter.serialize(orig)))

    def testRoundtripAscii(self):
        converter = StringConverter(wireSchema="ascii-string",
                                    encoding="ascii")
        orig = "foooo"
        self.assertEqual(orig,
                          converter.deserialize(*converter.serialize(orig)))

    def testCharsetErrors(self):
        asciiConverter = StringConverter(wireSchema="ascii-string",
                                         encoding="ascii")
        self.assertRaises(UnicodeEncodeError,
                          asciiConverter.serialize, "test"+chr(266))
        self.assertRaises(UnicodeDecodeError, asciiConverter.deserialize,
                          bytes(list(range(133))), 'ascii-string')


class ScopeConverterTest(unittest.TestCase):

    def testRoundTrip(self):
        converter = ScopeConverter()

        root = Scope('/foo/bar')
        self.assertEqual(root,
                         converter.deserialize(*converter.serialize(root)))

        someScope = Scope('/foo/bar')
        self.assertEqual(someScope,
                         converter.deserialize(*converter.serialize(someScope)))


class EventsByScopeMapConverterTest(unittest.TestCase):

    def testEmptyRoundtrip(self):

        data = {}
        converter = EventsByScopeMapConverter()
        self.assertEqual(data,
                          converter.deserialize(*converter.serialize(data)))

    def testRoundtrip(self):
        self.maxDiff = None

        data = {}
        scope1 = Scope("/a/test")
        event1 = Event(id=EventId(uuid4(), 32), scope=scope1,
                       method="foo", data=42, type=int,
                       userTimes={"foo": 1231234.0})
        event1.metaData.setSendTime()
        event1.metaData.setReceiveTime()
        event2 = Event(id=EventId(uuid4(), 1001), scope=scope1,
                       method="fooasdas", data=422, type=int,
                       userTimes={"bar": 1234.05})
        event2.metaData.setSendTime()
        event2.metaData.setReceiveTime()
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
            self.assertAlmostEqual(orig.metaData.createTime,
                                   converted.metaData.createTime,
                                   places=4)
            self.assertEqual(orig.causes, converted.causes)


def checkStructureBasedRountrip(converterName, values):
    converter = rsb.converter.__dict__[converterName]()
    for value in values:
        assert_equals(value,
                      converter.deserialize(*converter.serialize(value)))


def test_structureBaseConverters():
    for converterName, values in [
            ('DoubleConverter', [0.0, -1.0, 1.0]),
            ('FloatConverter', [0.0, -1.0, 1.0]),
            ('Int32Converter', [0, -1, 1, -24378, ((1 << 31) - 1)]),
            ('Int64Converter', [0, -1, 1, -24378, ((1 << 63) - 1)]),
            ('Uint32Converter', [0, 1, 24378, ((1 << 32) - 1)]),
            ('Uint64Converter', [0, 1, 24378, ((1 << 32) - 1)]),
            ('BoolConverter', [True, False])]:
        yield checkStructureBasedRountrip, converterName, values
