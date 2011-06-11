# Copyright (C) 2011 Jan Moringen
#
# This Program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This Program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses>.

import unittest
import re

from rsb.transport.converter import Converter, StringConverter, ConverterMap, UnambiguousConverterMap, PredicateConverterList

class ConflictingStringConverter(Converter):
    def __init__(self):
        Converter.__init__(self, wireType=bytearray, wireSchema="utf-8-string", dataType=float)

    def serialize(self, input):
        return str(input)

    def deserialize(self, input):
        return str(input)

class ConverterMapTest(unittest.TestCase):
    def testAddConverter(self):
        map = ConverterMap(str)
        map.addConverter(StringConverter())
        map.addConverter(ConflictingStringConverter())
        self.assertRaises(Exception, map.addConverter, StringConverter())
        map.addConverter(StringConverter(), override=True)

class UnambiguousConverterMapTest(unittest.TestCase):
    def testAddConverter(self):
        map = UnambiguousConverterMap(str)
        map.addConverter(StringConverter())
        self.assertRaises(Exception, map.addConverter, ConflictingStringConverter())
        self.assertRaises(Exception, map.addConverter, ConflictingStringConverter(), True)
        map.addConverter(StringConverter(), override=True)


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

class StringConverterTest(unittest.TestCase):
    
    def testRoundtripUtf8(self):
        converter = StringConverter()
        orig = u"asd" + unichr(270) + unichr(40928)
        self.assertEquals(orig, converter.deserialize(converter.serialize(orig)))
        orig = "i am a normal string"
        self.assertEquals(orig, converter.deserialize(converter.serialize(orig)))
    
    def testRoundtripAscii(self):
        converter = StringConverter(wireSchema="ascii-string", encoding="ascii", dataType=str)
        orig = "foooo"
        self.assertEquals(orig, converter.deserialize(converter.serialize(orig)))

    def testCharsetErrors(self):
        asciiConverter = StringConverter(wireSchema="ascii-string", encoding="ascii")
        self.assertRaises(UnicodeEncodeError, asciiConverter.serialize, u"test"+unichr(266))
        self.assertRaises(UnicodeDecodeError, asciiConverter.deserialize, bytearray(range(133)))

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(ConverterMapTest))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(UnambiguousConverterMapTest))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(PredicateConverterListTest))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(StringConverterTest))
    return suite
