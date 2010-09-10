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
from rsb import EventProcessor, Subscription, RSBEvent
from rsb.filter import RecordingTrueFilter, RecordingFalseFilter

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
        
    def testType(self):
        t = "asdasd"
        self.e.type = t
        self.assertEqual(t, self.e.type)
        
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
        
    def testGetSetFilters(self):
        
        f1 = 42
        f2 = 84
        
        s = rsb.Subscription()
        s.appendFilter(f1)
        s.appendFilter(f2)
        
        self.assertTrue(f1 in s.getFilters())
        self.assertTrue(f2 in s.getFilters())

class EventProcessorTest(unittest.TestCase):
    
    def testProcess(self):
        
        ep = EventProcessor(5)
        
        matchingCalls1 = []
        matchingCalls2 = []
        
        def matchingAction1(event):
            matchingCalls1.append(event)
        def matchingAction2(event):
            matchingCalls2.append(event)
        
        matchingRecordingFilter1 = RecordingTrueFilter()
        matchingRecordingFilter2 = RecordingTrueFilter()
        matching = Subscription()
        matching.appendFilter(matchingRecordingFilter1)
        matching.appendFilter(matchingRecordingFilter2)
        matching.appendAction(matchingAction1)
        matching.appendAction(matchingAction2)
        
        noMatchCalls = []
        def noMatchAction(event):
            noMatchCalls.append(event)
        
        noMatch = Subscription()
        noMatchRecordingFilter = RecordingFalseFilter()
        noMatch.appendFilter(noMatchRecordingFilter)
        noMatch.appendAction(noMatchAction)
        
        event1 = RSBEvent()
        event2 = RSBEvent()
        event3 = RSBEvent()
        
        ep.subscribe(matching)
        ep.subscribe(noMatch)
        
        ep.process(event1)
        ep.process(event2)
        ep.unsubscribe(matching)
        ep.process(event3)
        
        # both filters must have been called
        self.assertEqual(2, len(matchingRecordingFilter1.events))
        self.assertTrue(event1 in matchingRecordingFilter1.events)
        self.assertTrue(event2 in matchingRecordingFilter1.events)
        
        self.assertEqual(2, len(matchingRecordingFilter2.events))
        self.assertTrue(event1 in matchingRecordingFilter2.events)
        self.assertTrue(event2 in matchingRecordingFilter2.events)
        
        # both actions must have been called
        self.assertEqual(2, len(matchingCalls1))
        self.assertTrue(event1 in matchingCalls1)
        self.assertTrue(event2 in matchingCalls1)
        
        self.assertEqual(2, len(matchingCalls2))
        self.assertTrue(event1 in matchingCalls2)
        self.assertTrue(event2 in matchingCalls2)
        
        # noMatch subscriber must not have been called
        self.assertEqual(3, len(noMatchRecordingFilter.events))
        self.assertTrue(event1 in noMatchRecordingFilter.events)
        self.assertTrue(event2 in noMatchRecordingFilter.events)
        self.assertTrue(event3 in noMatchRecordingFilter.events)
        