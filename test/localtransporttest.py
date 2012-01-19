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

from rsb.transport.local import Bus
from rsb import Scope, Event

class BusTest(unittest.TestCase):
    
    class StubSink(object):
        
        def __init__(self, scope):
            self.scope = scope
            self.events = []
            
        def handle(self, event):
            self.events.append(event)

    def testConstruction(self):
        Bus()
        
    def testNotifyHierarchy(self):
        bus = Bus()
        
        targetScope = Scope("/this/is/a/test")
        scopes = targetScope.superScopes(True)
        sinksByScope = {}
        for scope in scopes:
            sinksByScope[scope] = self.StubSink(scope)
            bus.addSink(sinksByScope[scope])
            
        notNotifiedSiblingSink = self.StubSink(Scope("/not/notified"))
        bus.addSink(notNotifiedSiblingSink)
        notNotifiedChildSink = self.StubSink(targetScope.concat(Scope("/child")))
        bus.addSink(notNotifiedChildSink)
            
        event = Event(scope=targetScope)
        bus.handle(event)
        for scope, sink in sinksByScope.items():
            self.assertTrue(event in sink.events)
            self.assertEqual(1, len(sink.events))

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(BusTest))
    return suite
