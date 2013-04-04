# ============================================================
#
# Copyright (C) 2011, 2013 Jan Moringen
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
from rsb.converter import Converter, NoneConverter, StringConverter, ConverterMap, UnambiguousConverterMap, PredicateConverterList

class ConflictingStringConverter(Converter):
    def __init__(self):
        Converter.__init__(self, wireType=bytearray, wireSchema="utf-8-string", dataType=float)

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
        self.assertRaises(Exception, map.addConverter, ConflictingStringConverter())
        self.assertRaises(Exception, map.addConverter, ConflictingStringConverter(), True)
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
        regex.addConverter(v1,
                           wireSchemaPredicate=lambda wireSchema: re.match(".*foo.*", wireSchema),
                           dataTypePredicate=lambda dataType:   re.match(".*foo.*", dataType))
        self.assertRaises(KeyError, regex.getConverterForWireSchema, "")
        self.assertRaises(KeyError, regex.getConverterForWireSchema, "bla")
        self.assertIs(regex.getConverterForWireSchema("foo"), v1)
        self.assertIs(regex.getConverterForWireSchema("foobar"), v1)
        self.assertRaises(KeyError, regex.getConverterForDataType, "")
        self.assertRaises(KeyError, regex.getConverterForDataType, "bla")
        self.assertIs(regex.getConverterForDataType("foo"), v1)
        self.assertIs(regex.getConverterForDataType("foobar"), v1)

        mixed = PredicateConverterList(str)
        mixed.addConverter(v1,
                           wireSchemaPredicate=lambda wireSchema: re.match(".*foo.*", wireSchema),
                           dataTypePredicate=lambda dataType:   re.match(".*foo.*", dataType))
        mixed.addConverter(v2,
                           wireSchemaPredicate=lambda wireSchema: True,
                           dataTypePredicate=lambda dataType:   True)
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
        self.assertEquals(None, converter.deserialize(*converter.serialize(None)))

class StringConverterTest(unittest.TestCase):

    def testRoundtripUtf8(self):
        converter = StringConverter()
        orig = u"asd" + unichr(270) + unichr(40928)
        self.assertEquals(orig, converter.deserialize(*converter.serialize(orig)))
        orig = "i am a normal string"
        self.assertEquals(orig, converter.deserialize(*converter.serialize(orig)))

    def testRoundtripAscii(self):
        converter = StringConverter(wireSchema="ascii-string", encoding="ascii", dataType=str)
        orig = "foooo"
        self.assertEquals(orig, converter.deserialize(*converter.serialize(orig)))

    def testCharsetErrors(self):
        asciiConverter = StringConverter(wireSchema="ascii-string", encoding="ascii")
        self.assertRaises(UnicodeEncodeError, asciiConverter.serialize, u"test"+unichr(266))
        self.assertRaises(UnicodeDecodeError, asciiConverter.deserialize,
                          bytearray(range(133)), 'ascii-string')

def makeStructBasedConverterTest(name, values):
    class NewTest(unittest.TestCase):
        def testRoundtrip(self):
            converter = rsb.converter.__dict__[name]()
            for value in values:
                self.assertEquals(value, converter.deserialize(*converter.serialize(value)))
    testName = name + 'Test'
    NewTest.__name__ = testName
    globals()[testName] = NewTest
    return NewTest


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(ConverterMapTest))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(UnambiguousConverterMapTest))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(PredicateConverterListTest))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(NoneConverterTest))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(StringConverterTest))

    for args in [ ('DoubleConverter', [ 0.0, -1.0, 1.0 ]),
                  ('FloatConverter',  [ 0.0, -1.0, 1.0 ]),
                  ('Int32Converter',  [ 0L, -1L, 1L, -24378L, ((1L << 31L) - 1L) ]),
                  ('Int64Converter',  [ 0L, -1L, 1L, -24378L, ((1L << 63L) - 1L) ]),
                  ('Uint32Converter', [ 0L, 1L, 24378L, ((1L << 32L) - 1L) ]),
                  ('Uint64Converter', [ 0L, 1L, 24378L, ((1L << 32L) - 1L) ]),
                  ('BoolConverter',   [ True, False ]) ]:
        suite.addTest(unittest.TestLoader()
                      .loadTestsFromTestCase(makeStructBasedConverterTest(*args)))

    return suite
