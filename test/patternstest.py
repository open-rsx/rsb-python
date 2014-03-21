# ============================================================
#
# Copyright (C) 2011, 2012, 2014 Jan Moringen <jmoringe@techfak.uni-bielefeld.DE>
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
import time
from threading import Condition

inProcessNoIntrospectionConfig = ParticipantConfig.fromDict({
    'introspection.enabled':        '0',
    'transport.inprocess.enabled' : '1'
})

class LocalServerTest (unittest.TestCase):
    def testConstruction(self):

        # Test creating a server without methods
        server = rsb.createServer('/some/scope',
                                  config = inProcessNoIntrospectionConfig)
        self.assertEqual(server.methods, [])
        server.deactivate()

        server = rsb.createServer(rsb.Scope('/some/scope'),
                                  config = inProcessNoIntrospectionConfig)
        self.assertEqual(server.methods, [])
        server.deactivate()

        # Test creating a server with directly specified methods
        server = rsb.createServer(rsb.Scope('/some/scope'),
                                  methods = [ ('foo', lambda x: x, str, str) ],
                                  config  = inProcessNoIntrospectionConfig)
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
                                  config = inProcessNoIntrospectionConfig)
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

        localServer = rsb.createServer(
            '/roundtrip',
            methods = [ ('addone', lambda x: long(x + 1), long, long) ],
            config  = inProcessNoIntrospectionConfig)

        remoteServer = rsb.createRemoteServer('/roundtrip', inProcessNoIntrospectionConfig)

        # Call synchronously
        self.assertEqual(map(remoteServer.addone, range(100)),
                         range(1, 101))

        # Call asynchronously
        self.assertEqual(map(lambda x: x.get(),
                             map(remoteServer.addone.async, range(100))),
                         range(1, 101))

        localServer.deactivate()
        remoteServer.deactivate()

    def testVoidMethods(self):

        localServer = rsb.createServer('/void', config = inProcessNoIntrospectionConfig)
        def nothing(e):
            pass
        localServer.addMethod("nothing", nothing, str)

        remoteServer = rsb.createRemoteServer('/void', inProcessNoIntrospectionConfig)

        future = remoteServer.nothing.async("test")
        try:
            future.get(1)
        finally:
            localServer.deactivate()
            remoteServer.deactivate()

    def testParallelCallOfOneMethod(self):

        class Counter(object):
            def __init__(self):
                self.value = 0
        maxParallelCalls = Counter()
        currentCalls = []
        callLock = Condition()

        try:
            localServer = rsb.createServer('/takesometime', config = inProcessNoIntrospectionConfig)
            def takeSomeTime(e):
                with callLock:
                    currentCalls.append(e)
                    maxParallelCalls.value = max(maxParallelCalls.value, len(currentCalls))
                    callLock.notifyAll()
                time.sleep(2)
                with callLock:
                    currentCalls.remove(e)
                    callLock.notifyAll()
            localServer.addMethod("takeSomeTime", takeSomeTime, str, allowParallelExecution=True)

            remoteServer = rsb.createRemoteServer('/takesometime', inProcessNoIntrospectionConfig)

            remoteServer.takeSomeTime.async("test1")
            remoteServer.takeSomeTime.async("test2")
            remoteServer.takeSomeTime.async("test3")

            numCalled = 0
            with callLock:
                while maxParallelCalls.value < 3 and numCalled < 5:
                    numCalled = numCalled + 1
                    callLock.wait()
                if numCalled == 5:
                    self.fail("Impossible to be called in parallel again")
                else:
                    self.assertEqual(3, maxParallelCalls.value)
        finally:
            try:
                localServer.deactivate()
            except:
                pass
            try:
                remoteServer.deactivate()
            except:
                pass

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(LocalServerTest))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(RoundTripTest))
    return suite
