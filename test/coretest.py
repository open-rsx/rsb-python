# ============================================================
#
# Copyright (C) 2010 by Johannes Wienke <jwienke at techfak dot uni-bielefeld dot de>
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

import os
import uuid

import unittest

import rsb
from rsb import Scope, QualityOfServiceSpec, ParticipantConfig, MetaData, Event, \
    Informer, EventId, setDefaultParticipantConfig, getDefaultParticipantConfig,\
    Participant
import time
from uuid import uuid4
from rsb.converter import Converter, registerGlobalConverter
from threading import Condition

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
        self.assertEqual(len(config.getTransports(includeDisabled=True)), 3)

        # Check spread transport
        transport = config.getTransport('spread')
        self.assertEqual(transport.getName(), 'spread')
        self.assertTrue(transport.isEnabled())

    def testFromEnvironment(self):
        os.environ = dict( (key, value) for (key, value) in os.environ.items()
                           if not 'RSB' in key )
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

        # Non-ASCII characters are not allowed. However, unicode
        # object consisting of acceptable characters are OK.
        Scope(u'/')
        Scope(u'/test')
        self.assertRaises(ValueError, Scope, u'/br\xc3\xb6tchen')

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

    def testHash(self):
        
        self.assertEqual(hash(Scope("/")), hash(Scope("/")))
        self.assertNotEqual(hash(Scope("/")), hash(Scope("/foo")))
        self.assertEqual(hash(Scope("/bla/foo")), hash(Scope("/bla/foo/")))

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

class EventIdTest(unittest.TestCase):

    def testHashing(self):

        id1 = EventId(uuid.uuid4(), 23)
        id2 = EventId(id1.getParticipantId(), 23)
        id3 = EventId(uuid.uuid4(), 32)
        id4 = EventId(id3.getParticipantId(), 33)

        self.assertEqual(hash(id1), hash(id2))
        self.assertNotEqual(hash(id1), hash(id3))
        self.assertNotEqual(hash(id1), hash(id4))
        self.assertNotEqual(hash(id3), hash(id4))

    def testGetAsUUID(self):

        id1 = EventId(uuid.uuid4(), 23)
        id2 = EventId(id1.participantId, 23)
        id3 = EventId(id1.participantId, 24)
        id4 = EventId(uuid.uuid4(), 24)

        self.assertEqual(id1.getAsUUID(), id2.getAsUUID())
        self.assertNotEqual(id1.getAsUUID(), id3.getAsUUID())
        self.assertNotEqual(id1.getAsUUID(), id4.getAsUUID())
        self.assertNotEqual(id3.getAsUUID(), id4.getAsUUID())

class EventTest(unittest.TestCase):

    def setUp(self):
        self.e = rsb.Event()

    def testConstructor(self):

        self.assertEqual(None, self.e.getData())
        self.assertEqual(Scope("/"), self.e.getScope())

    def testData(self):

        data = 42
        self.e.data = data
        self.assertEqual(data, self.e.data)

    def testScope(self):

        scope = Scope("/123/456")
        self.e.scope = scope
        self.assertEqual(scope, self.e.scope)

    def testType(self):
        t = "asdasd"
        self.e.type = t
        self.assertEqual(t, self.e.type)

    def testCauses(self):

        sid = uuid.uuid4()
        e = Event(EventId(sid, 32))
        self.assertEqual(0, len(e.causes))
        cause = EventId(uuid4(), 546345)
        e.addCause(cause)
        self.assertEqual(1, len(e.causes))
        self.assertTrue(e.isCause(cause))
        self.assertTrue(cause in e.causes)
        e.removeCause(cause)
        self.assertFalse(e.isCause(cause))
        self.assertEqual(0, len(e.causes))

    def testComparison(self):

        sid = uuid.uuid4()
        e1 = Event(EventId(sid, 0))
        e2 = Event(EventId(sid, 0))
        e2.getMetaData().setCreateTime(e1.getMetaData().getCreateTime())

        e1.metaData.setUserTime("foo")
        self.assertNotEquals(e1, e2)
        e2.metaData.setUserTime("foo", e1.getMetaData().getUserTimes()["foo"])
        self.assertEquals(e1, e2)

        cause = EventId(uuid4(), 42)
        e1.addCause(cause)
        self.assertNotEqual(e1, e2)
        e2.addCause(cause)
        self.assertEqual(e1, e2)

class FactoryTest(unittest.TestCase):

    def setUp(self):
        config = ParticipantConfig.fromDict({"transport.inprocess.enabled": "1"})
        setDefaultParticipantConfig(config)

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

class InformerTest(unittest.TestCase):

    def setUp(self):
        self.defaultScope = Scope("/a/test")
        self.informer = Informer(self.defaultScope, str)

    def tearDown(self):
        self.informer.deactivate()

    def testSendEventWrongScope(self):
        # Error: unrelated scope
        e = Event(scope = Scope("/blubb"), data = 'foo', type = self.informer.type)
        self.assertRaises(ValueError, self.informer.publishEvent, e)

        # OK: identical scope
        e = Event(scope = self.defaultScope, data = 'foo', type = self.informer.type)
        self.informer.publishEvent(e)

        # OK: sub-scope
        e = Event(scope = self.defaultScope.concat(Scope('/sub')),
                  data  = 'foo',
                  type  = self.informer.type)
        self.informer.publishEvent(e)

    def testSendEventWrongType(self):
        # Wrong type
        e = Event(scope = self.defaultScope, data = 5)
        self.assertRaises(ValueError, self.informer.publishEvent, e)

        # Wrong type
        self.assertRaises(ValueError, self.informer.publishData, 5.0)

        # OK
        self.informer.publishData('bla')

class IntegrationTest(unittest.TestCase):

    def testLazyConverterRegistration(self):
        """
        Test that converters can be added to the global converter map without
        requiring a completely new instance of the default participant config.
        """
        
        # prevent changes to the configuration from other tests
        setDefaultParticipantConfig(config=ParticipantConfig.fromDict({"transport.socket.enabled": "1"}))

        class FooType(object):
            """
            Dummy data type for the test
            """

        class FooTypeConverter(Converter):
            def __init__(self):
                Converter.__init__(self, bytearray, FooType, "footype")
            def serialize(self, inp):
                return bytearray(), self.wireSchema
            def deserialize(self, inp, wireSchema):
                return FooType()

        registerGlobalConverter(FooTypeConverter())

        config = getDefaultParticipantConfig() 
        # this will raise an exception if the converter is not available.
        # This assumes that socket transport is enabled as the only transport
        self.assertTrue(isinstance(Participant.getConnectors('out', config)[0].getConverterForDataType(FooType), FooTypeConverter))

class ContextManagerTest(unittest.TestCase):

    def setUp(self):
        self.scope = rsb.Scope('/one/test')
        self.receivedCondition = Condition()
        self.receivedData = None
    
    def testInformerListenerRoundtrip(self):
        
        with rsb.createInformer(self.scope, dataType=str) as informer, \
             rsb.createListener(self.scope) as listener:
            def setReceived(event):
                with self.receivedCondition:
                    self.receivedData = event.data
                    self.receivedCondition.notifyAll()
            listener.addHandler(setReceived)
            data = 'our little test'
            informer.publishData(data)
            with self.receivedCondition:
                while self.receivedData is None:
                    self.receivedCondition.wait()
                self.assertEqual(data, self.receivedData)

    def testRpcRoundtrip(self):
        
        with rsb.createServer(self.scope) as server, \
             rsb.createRemoteServer(self.scope) as client:
            
            methodName = 'test'
            data = 'bla'
            
            server.addMethod(methodName, lambda x: x, str, str)
            self.assertEqual(data, client.test(data))

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(ParticipantConfigTest))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(QualityOfServiceSpecTest))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(ScopeTest))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(EventIdTest))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(EventTest))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(FactoryTest))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(MetaDataTest))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(InformerTest))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(IntegrationTest))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(ContextManagerTest))
    return suite
