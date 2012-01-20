# ============================================================
#
# Copyright (C) 2012 by Johannes Wienke <jwienke at techfak dot uni-bielefeld dot de>
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

from rsb.transport.local import Bus, OutConnector, InConnector
from rsb import Scope, Event
import time
from transporttest import TransportTest

class StubSink(object):
    
    def __init__(self, scope):
        self.scope = scope
        self.events = []
        
    def getScope(self):
        return self.scope
        
    def handle(self, event):
        self.events.append(event)
        
    def __call__(self, event):
        self.handle(event)

class BusTest(unittest.TestCase):

    def testConstruction(self):
        Bus()
        
    def testNotifyHierarchy(self):
        bus = Bus()
        
        targetScope = Scope("/this/is/a/test")
        scopes = targetScope.superScopes(True)
        sinksByScope = {}
        for scope in scopes:
            sinksByScope[scope] = StubSink(scope)
            bus.addSink(sinksByScope[scope])
            
        notNotifiedSiblingSink = StubSink(Scope("/not/notified"))
        bus.addSink(notNotifiedSiblingSink)
        notNotifiedChildSink = StubSink(targetScope.concat(Scope("/child")))
        bus.addSink(notNotifiedChildSink)
            
        event = Event(scope=targetScope)
        bus.handle(event)
        for scope, sink in sinksByScope.items():
            self.assertTrue(event in sink.events)
            self.assertEqual(1, len(sink.events))

class OutConnectorTest(unittest.TestCase):
    
    def testConstruction(self):
        OutConnector()
        
    def testHandle(self):
        
        bus = Bus()
        connector = OutConnector(bus=bus)
        
        scope = Scope("/a/test")
        sink = StubSink(scope)
        bus.addSink(sink)
        
        e = Event()
        e.scope = scope
        
        before = time.time()
        connector.handle(e)
        after = time.time()
        self.assertEqual(1, len(sink.events))
        self.assertTrue(e in sink.events)
        self.assertGreaterEqual(e.metaData.sendTime, before)
        self.assertLessEqual(e.metaData.sendTime, after)
        
class InConnectorTest(unittest.TestCase):
    
    def testConstruction(self):
        InConnector()
    
    def testPassToAction(self):
        
        scope = Scope("/lets/go")

        bus = Bus()
        connector = InConnector(bus=bus)
        connector.setScope(scope)
        connector.activate()
        
        action = StubSink(scope)
        connector.setObserverAction(action)
        
        e = Event()
        e.scope = scope
        bus.handle(e)
        self.assertEqual(1, len(action.events))
        self.assertTrue(e in action.events)
                
class LocalTransportTest(TransportTest):
    
    def _getInConnector(self, scope, activate=True):
        connector = InConnector()
        connector.setScope(scope)
        if activate:
            connector.activate()
        return connector
    
    def _getOutConnector(self, scope, activate=True):
        connector = OutConnector()
        connector.setScope(scope)
        if activate:
            connector.activate()
        return connector
        
def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(BusTest))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(OutConnectorTest))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(InConnectorTest))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(LocalTransportTest))
    return suite
