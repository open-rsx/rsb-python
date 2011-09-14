# ============================================================
#
# Copyright (C) 2011 Jan Moringen <jmoringe@techfak.uni-bielefeld.DE>
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
import rsb

class LocalServerTest (unittest.TestCase):
    def testConstruction(self):
        # Test creating a server without methods
        server = rsb.createServer('/some/scope')
        self.assertEqual(server.methods, [])

        server = rsb.createServer(rsb.Scope('/some/scope'))
        self.assertEqual(server.methods, [])

        # Test creating a server with directly specified methods
        server = rsb.createServer(rsb.Scope('/some/scope'),
                                  methods = [ ('foo', lambda x: x, str, str) ])
        self.assertEqual([ m.name for m in server.methods ], [ 'foo' ])

        # Test creating a server that exposes method of an existing
        # object
        class SomeClass (object):
            def bar(x):
                pass

        someObject = SomeClass()
        server = rsb.createServer(rsb.Scope('/some/scope'),
                                  object = someObject,
                                  expose = [ ('bar', str, None) ])
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

class RoundTripTest (unittest.TestCase):
    def testRoundTrip(self):
        localServer = rsb.createServer(
            '/roundtrip',
            methods = [ ('addone', lambda x: x + 1, long, long) ])

        remoteServer = rsb.createRemoteServer('/roundtrip')

        # Call synchronously
        self.assertEqual(map(remoteServer.addone, range(100)),
                         range(1, 101))

        # Call asynchronously
        self.assertEqual(map(lambda x: x.get(),
                             map(remoteServer.addone.async, range(100))),
                         range(1, 101))

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(LocalServerTest))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(RoundTripTest))
    return suite
