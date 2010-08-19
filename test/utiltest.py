# ============================================================
#
# Copyright (C) 2010 by Johannes Wienke <jwienke at techfak dot uni-bielefeld dot de>
#
# This program is free software; you can redistribute it
# and/or modify it under the terms of the GNU General
# Public License as published by the Free Software Foundation;
# either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# ============================================================

import unittest

import rsb.util

class EnumValueTest(unittest.TestCase):
    
    def testCompare(self):
        
        val1 = rsb.util.Enum.EnumValue("TEST")
        val2 = rsb.util.Enum.EnumValue("OTHER")
        self.assertNotEqual(val1, val2)
        
        val2 = rsb.util.Enum.EnumValue("TEST")
        self.assertEqual(val1, val2)
        
    def testStr(self):
        
        self.assertEqual("TEST", str(rsb.util.Enum.EnumValue("TEST")))

class EnumTest(unittest.TestCase):
    
    def testEnum(self):
        
        e = rsb.util.Enum("e", ["A", "B", "C"])
        
        self.assertEqual(rsb.util.Enum.EnumValue("A"), e.A)
        self.assertEqual(rsb.util.Enum.EnumValue("B"), e.B)
        self.assertEqual(rsb.util.Enum.EnumValue("C"), e.C)
        
        self.assertEqual("Enum e: A, B, C", str(e))
