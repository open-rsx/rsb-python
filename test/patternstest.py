# ============================================================
#
# Copyright (C) 2011, 2012 Jan Moringen <jmoringe@techfak.uni-bielefeld.DE>
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
import rsb
from rsb import ParticipantConfig

class LocalServerTest (unittest.TestCase):
    def testConstruction(self):

        # Test creating a server without methods
        server = rsb.createServer('/some/scope', config=ParticipantConfig.fromDict({"transport.inprocess.enabled" : "1"}))
        self.assertEqual(server.methods, [])
        server.deactivate()

        server = rsb.createServer(rsb.Scope('/some/scope'), config=ParticipantConfig.fromDict({"transport.inprocess.enabled" : "1"}))
        self.assertEqual(server.methods, [])
        server.deactivate()

        # Test creating a server with directly specified methods
        server = rsb.createServer(rsb.Scope('/some/scope'),
                                  methods = [ ('foo', lambda x: x, str, str) ], config=ParticipantConfig.fromDict({"transport.inprocess.enabled" : "1"}))
        self.assertEqual([ m.name for m in server.methods ], [ 'foo' ])
        server.deactivate()

        # Test creating a server that exposes method of an existing
        # object
        class SomeClass (object):
            def bar(x):
                pass

        someObject = SomeClass()
        server = rsb.createServer(rsb.Scope('/some/scope'),
                                  object = someObject,
                                  expose = [ ('bar', str, None) ],
                                  config=ParticipantConfig.fromDict({"transport.inprocess.enabled" : "1"}))
        self.assertEqual([ m.name for m in server.methods ], [ 'bar' ])

        # Cannot supply expose without object
        self.assertRaises(ValueError,
                          rsb.createServer,
                          '/some/scope',
                          expose  = [ ('bar', str, None) ])

        # Cannot supply these simultaneously
        self.assertRaises(ValueError,
                          rsb.createServer,
                          '/some/scope',
                          object  = someObject,
                          expose  = [ ('bar', str, None) ],
                          methods = [ ('foo', lambda x: x, str, str) ])
        server.deactivate()

class RoundTripTest (unittest.TestCase):
    def testRoundTrip(self):

        config = ParticipantConfig.fromDict({"transport.inprocess.enabled" : "1"})

        localServer = rsb.createServer(
            '/roundtrip',
            methods = [ ('addone', lambda x: long(x + 1), long, long) ], config=config)

        remoteServer = rsb.createRemoteServer('/roundtrip', config)

        # Call synchronously
        self.assertEqual(map(remoteServer.addone, range(100)),
                         range(1, 101))

        # Call asynchronously
        self.assertEqual(map(lambda x: x.get(),
                             map(remoteServer.addone.async, range(100))),
                         range(1, 101))

        localServer.deactivate()
        remoteServer.deactivate()

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(LocalServerTest))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(RoundTripTest))
    return suite
