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
from rsb import Scope, QualityOfServiceSpec, ParticipantConfig, MetaData, Event
import time

class ParticipantConfigTest (unittest.TestCase):

    def testConstruction(self):
        ParticipantConfig()

    def testFromFile(self):
        config = ParticipantConfig.fromFile('test/smoke-test.conf')

        # Check quality of service specs
        self.assertEqual(config.getQualityOfServiceSpec().getReliability(),
                         QualityOfServiceSpec.Reliability.UNRELIABLE)
        self.assertEqual(config.getQualityOfServiceSpec().getOrdering(),
                         QualityOfServiceSpec.Ordering.UNORDERED)

        self.assertEqual(len(config.getTransports()), 1)
        self.assertEqual(len(config.getTransports(includeDisabled=True)), 1)

        # Check spread transport
        transport = config.getTransport('spread')
        self.assertEqual(transport.getName(), 'spread')
        self.assertTrue(transport.isEnabled())

        # Check converters of spread transport
        converters = transport.getConverters()
        self.assertTrue(converters.getConverterForWireSchema('string'))
        self.assertTrue(converters.getConverterForDataType(str))
        # not yet
        #self.assertTrue(converters.getConverterForWireSchema('bool'))
        #self.assertTrue(converters.getConverterForDataType(bool))

    def testFromEnvironment(self):
        os.environ['RSB_QUALITYOFSERVICE_RELIABILITY'] = 'UNRELIABLE'
        os.environ['RSB_QUALITYOFSERVICE_ORDERED'] = 'UNORDERED'
        os.environ['RSB_TRANSPORT_SPREAD_ENABLED'] = 'yes'

        config = ParticipantConfig.fromEnvironment()

        # Check quality of service specs
        self.assertEqual(config.getQualityOfServiceSpec().getReliability(),
                         QualityOfServiceSpec.Reliability.UNRELIABLE)
        self.assertEqual(config.getQualityOfServiceSpec().getOrdering(),
                         QualityOfServiceSpec.Ordering.UNORDERED)

        self.assertEqual(len(config.getTransports()), 1)
        self.assertEqual(len(config.getTransports(includeDisabled=True)), 1)

        # Check spread transport
        transport = config.getTransport('spread')
        self.assertEqual(transport.getName(), 'spread')
        self.assertTrue(transport.isEnabled())

        # Check converters of spread transport
        converters = transport.getConverters()
        self.assertTrue(converters.getConverterForWireSchema('string'))
        self.assertTrue(converters.getConverterForDataType(str))
        # not yet
        #self.assertTrue(converters.getConverterForWireSchema('bool'))
        #self.assertTrue(converters.getConverterForDataType(bool))


    def testOverwritingDefaults(self):
        defaults = { 'transport.spread.enabled':     'yes',
                     'qualityofservice.reliability': 'UNRELIABLE' }
        config = ParticipantConfig.fromDict(defaults)
        self.assertEqual(config.getQualityOfServiceSpec().getReliability(),
                         QualityOfServiceSpec.Reliability.UNRELIABLE)
        self.assertTrue(config.getTransport('spread').isEnabled())

        os.environ['RSB_QUALITYOFSERVICE_RELIABILITY'] = 'RELIABLE'
        os.environ['RSB_TRANSPORT_SPREAD_ENABLED'] = 'no'
        config = ParticipantConfig.fromEnvironment(defaults)

        # Check overwritten values
        self.assertEqual(config.getQualityOfServiceSpec().getReliability(),
                         QualityOfServiceSpec.Reliability.RELIABLE)
        self.assertFalse(config.getTransport('spread').isEnabled())

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

class EventTest(unittest.TestCase):

    def setUp(self):
        self.e = rsb.Event()

    def testConstructor(self):

        self.assertEqual(None, self.e.getData())
        self.assertEqual(Scope("/"), self.e.getScope())
        self.assertEqual(type(self.e.getId()), uuid.UUID)

    def testData(self):

        data = 42
        self.e.data = data
        self.assertEqual(data, self.e.data)

    def testScope(self):

        scope = Scope("/123/456")
        self.e.scope = scope
        self.assertEqual(scope, self.e.scope)

    def testId(self):

        id = uuid.uuid4()
        self.e.id = id
        self.assertEqual(id, self.e.id)

    def testType(self):
        t = "asdasd"
        self.e.type = t
        self.assertEqual(t, self.e.type)
        
    def testComparison(self):
        
        e1 = Event()
        e2 = Event()
        e2.getMetaData().setCreateTime(e1.getMetaData().getCreateTime())
        # still distinct id
        self.assertNotEquals(e1, e2)
        e2.setId(e1.getId())
        self.assertEquals(e1, e2)
        
        e1.metaData.setUserTime("foo")
        self.assertNotEquals(e1, e2)
        e2.metaData.setUserTime("foo", e1.getMetaData().getUserTimes()["foo"])
        self.assertEquals(e1, e2)

class FactoryTest(unittest.TestCase):
    def testDefaultParticipantConfig(self):
        self.assert_(rsb.getDefaultParticipantConfig())

    def testCreateListener(self):
        self.assert_(rsb.createListener("/"))

    def testCreateInformer(self):
        self.assert_(rsb.createInformer("/"))

class MetaDataTest(unittest.TestCase):

    def testConstruction(self):

        before = time.time();
        meta = MetaData()
        after = time.time()

        self.assertTrue(meta.getCreateTime() != None)
        self.assertTrue(meta.getSendTime() == None)
        self.assertTrue(meta.getReceiveTime() == None)
        self.assertTrue(meta.getDeliverTime() == None)

        self.assertTrue(meta.getCreateTime() >= before)
        self.assertTrue(meta.getCreateTime() <= after)

    def testTimesAuto(self):

        meta = MetaData()

        before = time.time();

        meta.setCreateTime(None)
        meta.setSendTime(None)
        meta.setReceiveTime(None)
        meta.setDeliverTime(None)

        after = time.time();

        self.assertNotEquals(None, meta.getCreateTime())
        self.assertNotEquals(None, meta.getSendTime())
        self.assertNotEquals(None, meta.getReceiveTime())
        self.assertNotEquals(None, meta.getDeliverTime())

        self.assertTrue(before <= meta.getCreateTime())
        self.assertTrue(before <= meta.getSendTime())
        self.assertTrue(before <= meta.getReceiveTime())
        self.assertTrue(before <= meta.getDeliverTime())

        self.assertTrue(after >= meta.getCreateTime())
        self.assertTrue(after >= meta.getSendTime())
        self.assertTrue(after >= meta.getReceiveTime())
        self.assertTrue(after >= meta.getDeliverTime())

    def testUserTimes(self):

        meta = MetaData()

        before = time.time();
        meta.setUserTime("foo")
        after = time.time();

        self.assertNotEquals(None, meta.userTimes["foo"])
        self.assertTrue(meta.userTimes["foo"] >= before)
        self.assertTrue(meta.userTimes["foo"] <= after)
        
    def testComparison(self):
        
        meta1 = MetaData()
        meta2 = MetaData()
        meta2.setCreateTime(meta1.getCreateTime())
        self.assertEquals(meta1, meta2)
        
        meta1.setCreateTime(213123)
        self.assertNotEquals(meta1, meta2)
        meta2.setCreateTime(meta1.getCreateTime())
        self.assertEquals(meta1, meta2)
        
        meta1.setSendTime()
        self.assertNotEquals(meta1, meta2)
        meta2.setSendTime(meta1.getSendTime())
        self.assertEquals(meta1, meta2)
        
        meta1.setReceiveTime()
        self.assertNotEquals(meta1, meta2)
        meta2.setReceiveTime(meta1.getReceiveTime())
        self.assertEquals(meta1, meta2)
        
        meta1.setDeliverTime()
        self.assertNotEquals(meta1, meta2)
        meta2.setDeliverTime(meta1.getDeliverTime())
        self.assertEquals(meta1, meta2)
        
        meta1.setUserTime("foo")
        self.assertNotEquals(meta1, meta2)
        meta2.setUserTime("foo", meta1.getUserTimes()["foo"])
        self.assertEquals(meta1, meta2)
        
        meta1.setUserInfo("foox", "bla")
        self.assertNotEquals(meta1, meta2)
        meta2.setUserInfo("foox", meta1.getUserInfos()["foox"])
        self.assertEquals(meta1, meta2)

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(ParticipantConfigTest))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(QualityOfServiceSpecTest))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(ScopeTest))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(EventTest))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(FactoryTest))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(MetaDataTest))
    return suite
