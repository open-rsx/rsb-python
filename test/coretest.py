# ============================================================
#
# Copyright (C) 2010 by Johannes Wienke <jwienke at techfak dot uni-bielefeld dot de>
#
# This program is free software you can redistribute it
# and/or modify it under the terms of the GNU General
# Public License as published by the Free Software Foundation
# either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# ============================================================

import os
import uuid

import unittest

import rsb
from rsb import EventProcessor, Subscription, RSBEvent, Scope, QualityOfServiceSpec, ParticipantConfig
from rsb.filter import RecordingTrueFilter, RecordingFalseFilter
import time
from threading import Condition

######################################################################
#
# Unit Tests
#
######################################################################

import unittest

class ParticipantConfigTest (unittest.TestCase):
    def testConstruction(self):
        config = ParticipantConfig()

    def testFromFile(self):
        pass

    def testFromEnvironment(self):
        os.environ['RSB_TRANSPORT_SPREAD_CONVERTER_FOO'] = 'bar'

    def testFromDefaultSource(self):
        # TODO how to test this?
        pass

class QualityOfServiceSpecTest(unittest.TestCase):

    def testConstruction(self):

        specs = QualityOfServiceSpec()
        self.assertEqual(QualityOfServiceSpec.Ordering.UNORDERED, specs.getOrdering())
        self.assertEqual(QualityOfServiceSpec.Reliability.RELIABLE, specs.getReliability())

    def testComparison(self):

        self.assertEqual(QualityOfServiceSpec(QualityOfServiceSpec.Ordering.UNORDERED, QualityOfServiceSpec.Reliability.RELIABLE), QualityOfServiceSpec())

class ScopeTest(unittest.TestCase):

    def testParsing(self):

        root = rsb.Scope("/")
        self.assertEqual(0, len(root.getComponents()))

        onePart = rsb.Scope("/test/")
        self.assertEqual(1, len(onePart.getComponents()))
        self.assertEqual("test", onePart.getComponents()[0])

        manyParts = rsb.Scope("/this/is/a/dumb3/test/")
        self.assertEqual(5, len(manyParts.getComponents()))
        self.assertEqual("this", manyParts.getComponents()[0])
        self.assertEqual("is", manyParts.getComponents()[1])
        self.assertEqual("a", manyParts.getComponents()[2])
        self.assertEqual("dumb3", manyParts.getComponents()[3])
        self.assertEqual("test", manyParts.getComponents()[4])

        # also ensure that the shortcut syntax works
        shortcut = rsb.Scope("/this/is")
        self.assertEqual(2, len(shortcut.getComponents()))
        self.assertEqual("this", shortcut.getComponents()[0])
        self.assertEqual("is", shortcut.getComponents()[1])

    def testParsingError(self):

        self.assertRaises(ValueError, rsb.Scope, "")
        self.assertRaises(ValueError, rsb.Scope, " ")
        self.assertRaises(ValueError, rsb.Scope, "/with space/does/not/work/")
        self.assertRaises(ValueError, rsb.Scope, "/with/do#3es/not43as/work/")
        self.assertRaises(ValueError, rsb.Scope, "/this//is/not/allowed/")
        self.assertRaises(ValueError, rsb.Scope, "/this/ /is/not/allowed/")

    def testToString(self):

        self.assertEqual("/", rsb.Scope("/").toString())
        self.assertEqual("/foo/", rsb.Scope("/foo/").toString())
        self.assertEqual("/foo/bar/", rsb.Scope("/foo/bar/").toString())
        self.assertEqual("/foo/bar/", rsb.Scope("/foo/bar").toString())

    def testConcat(self):

        self.assertEqual(rsb.Scope("/"), rsb.Scope("/").concat(rsb.Scope("/")))
        self.assertEqual(rsb.Scope("/a/test/"), rsb.Scope("/").concat(rsb.Scope("/a/test/")))
        self.assertEqual(rsb.Scope("/a/test/"), rsb.Scope("/a/test/").concat(rsb.Scope("/")))
        self.assertEqual(rsb.Scope("/a/test/example"), rsb.Scope("/a/test/").concat(rsb.Scope("/example/")))

    def testComparison(self):

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

    def testHierarchyComparison(self):

        self.assertTrue(rsb.Scope("/a/").isSubScopeOf(rsb.Scope("/")))
        self.assertTrue(rsb.Scope("/a/b/c/").isSubScopeOf(rsb.Scope("/")))
        self.assertTrue(rsb.Scope("/a/b/c/").isSubScopeOf(rsb.Scope("/a/b/")))
        self.assertFalse(rsb.Scope("/a/b/c/").isSubScopeOf(rsb.Scope("/a/b/c/")))
        self.assertFalse(rsb.Scope("/a/b/c/").isSubScopeOf(rsb.Scope("/a/b/c/d/")))
        self.assertFalse(rsb.Scope("/a/x/c/").isSubScopeOf(rsb.Scope("/a/b/")))

        self.assertTrue(rsb.Scope("/").isSuperScopeOf(rsb.Scope("/a/")))
        self.assertTrue(rsb.Scope("/").isSuperScopeOf(rsb.Scope("/a/b/c/")))
        self.assertTrue(rsb.Scope("/a/b/").isSuperScopeOf(rsb.Scope("/a/b/c/")))
        self.assertFalse(rsb.Scope("/a/b/c/").isSuperScopeOf(rsb.Scope("/a/b/c/")))
        self.assertFalse(rsb.Scope("/a/b/c/d/").isSuperScopeOf(rsb.Scope("/a/b/c/")))
        self.assertFalse(rsb.Scope("/b/").isSuperScopeOf(rsb.Scope("/a/b/c/")))

    def testSuperScopes(self):

        self.assertEqual(0, len(rsb.Scope("/").superScopes()))

        supers = rsb.Scope("/this/is/a/test/").superScopes()
        self.assertEqual(4, len(supers))
        self.assertEqual(rsb.Scope("/"), supers[0])
        self.assertEqual(rsb.Scope("/this/"), supers[1])
        self.assertEqual(rsb.Scope("/this/is/"), supers[2])
        self.assertEqual(rsb.Scope("/this/is/a/"), supers[3])

        supers = rsb.Scope("/").superScopes(True)
        self.assertEqual(1, len(supers))
        self.assertEqual(rsb.Scope("/"), supers[0])

        supers = rsb.Scope("/this/is/a/test/").superScopes(True)
        self.assertEqual(5, len(supers))
        self.assertEqual(rsb.Scope("/"), supers[0])
        self.assertEqual(rsb.Scope("/this/"), supers[1])
        self.assertEqual(rsb.Scope("/this/is/"), supers[2])
        self.assertEqual(rsb.Scope("/this/is/a/"), supers[3])
        self.assertEqual(rsb.Scope("/this/is/a/test/"), supers[4])

class RSBEventTest(unittest.TestCase):

    def setUp(self):
        self.e = rsb.RSBEvent()

    def testConstructor(self):

        self.assertEqual(None, self.e.getData())
        self.assertEqual(Scope("/"), self.e.getScope())
        self.assertEqual(type(self.e.getUUID()), uuid.UUID)

    def testData(self):

        data = 42
        self.e.data = data
        self.assertEqual(data, self.e.data)

    def testScope(self):

        scope = Scope("/123/456")
        self.e.scope = scope
        self.assertEqual(scope, self.e.scope)

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

        mc1Cond = Condition()
        matchingCalls1 = []
        mc2Cond = Condition()
        matchingCalls2 = []

        def matchingAction1(event):
            with mc1Cond:
                matchingCalls1.append(event)
                mc1Cond.notifyAll()
        def matchingAction2(event):
            with mc2Cond:
                matchingCalls2.append(event)
                mc2Cond.notifyAll()

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

        # both filters must have been called
        with matchingRecordingFilter1.condition:
            while len(matchingRecordingFilter1.events) < 2:
                matchingRecordingFilter1.condition.wait()

            self.assertEqual(2, len(matchingRecordingFilter1.events))
            self.assertTrue(event1 in matchingRecordingFilter1.events)
            self.assertTrue(event2 in matchingRecordingFilter1.events)

        with matchingRecordingFilter2.condition:
            while len(matchingRecordingFilter2.events) < 2:
                matchingRecordingFilter2.condition.wait()

            self.assertEqual(2, len(matchingRecordingFilter2.events))
            self.assertTrue(event1 in matchingRecordingFilter2.events)
            self.assertTrue(event2 in matchingRecordingFilter2.events)

        # both actions must have been called
        with mc1Cond:
            while len(matchingCalls1) < 2:
                mc1Cond.wait()
            self.assertEqual(2, len(matchingCalls1))
            self.assertTrue(event1 in matchingCalls1)
            self.assertTrue(event2 in matchingCalls1)

        with mc2Cond:
            while len(matchingCalls2) < 2:
                mc2Cond.wait()
            self.assertEqual(2, len(matchingCalls2))
            self.assertTrue(event1 in matchingCalls2)
            self.assertTrue(event2 in matchingCalls2)

        ep.unsubscribe(matching)
        ep.process(event3)

        # noMatch subscriber must not have been called
        with noMatchRecordingFilter.condition:
            while len(noMatchRecordingFilter.events) < 3:
                noMatchRecordingFilter.condition.wait()
            self.assertEqual(3, len(noMatchRecordingFilter.events))
            self.assertTrue(event1 in noMatchRecordingFilter.events)
            self.assertTrue(event2 in noMatchRecordingFilter.events)
            self.assertTrue(event3 in noMatchRecordingFilter.events)

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(ParticipantConfigTest))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(QualityOfServiceSpecTest))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(ScopeTest))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(RSBEventTest))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(SubscriptionTest))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(EventProcessorTest))
    return suite
