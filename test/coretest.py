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

import uuid

import unittest

import rsb

class RSBEventTest(unittest.TestCase):
    
    def setUp(self):
        self.e = rsb.RSBEvent()
    
    def testConstructor(self):
        
        self.assertEqual(None, self.e.getData())
        self.assertEqual("", self.e.getURI())
        self.assertEqual(type(self.e.getUUID()), uuid.UUID)
        
    def testData(self):
        
        data = 42
        self.e.data = data
        self.assertEqual(data, self.e.data)
        
    def testURI(self):
        
        uri = "123/456"
        self.e.uri = uri
        self.assertEqual(uri, self.e.uri)
    
    def testUUID(self):
        
        id = uuid.uuid1()
        self.e.uuid = id
        self.assertEqual(id, self.e.uuid)
        
class SubscriptionTest(unittest.TestCase):
    
    def setUp(self):
        self.s = rsb.Subscription()
        
    def testFilterMatching(self):
        
        e = rsb.RSBEvent()
        self.assertTrue(self.s.match(e))
        
        class DummyFilter:
            def match(self, event):
                return False
            
        self.s.appendFilter(DummyFilter())
        self.assertFalse(self.s.match(e))

def suite():
    suites = [unittest.makeSuite(RSBEventTest)]
    return unittest.TestSuite(suites)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')