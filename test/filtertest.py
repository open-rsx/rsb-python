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

import unittest
import uuid
import rsb
from rsb import Scope
import rsb.filter

class ScopeFilterTest(unittest.TestCase):

    def testMatch(self):

        scope = Scope("/bla")
        f = rsb.filter.ScopeFilter(scope)
        self.assertEqual(scope, f.getScope())

        e = rsb.Event()
        e.scope = scope
        self.assertTrue(f.match(e))
        e.scope = scope.concat(Scope("/sub/scope"))
        self.assertTrue(f.match(e))

        e.scope = Scope("/blubbbbbb")
        self.assertFalse(f.match(e))

class OriginFilterTest (unittest.TestCase):
    def testMatch(self):
        senderId1 = uuid.uuid1()
        e1 = rsb.Event(id = rsb.EventId(participantId  = senderId1,
                                        sequenceNumber = 0))
        senderId2 = uuid.uuid1()
        e2 = rsb.Event(id = rsb.EventId(participantId  = senderId2,
                                        sequenceNumber = 1))

        f = rsb.filter.OriginFilter(origin = senderId1)
        self.assertTrue(f.match(e1))
        self.assertFalse(f.match(e2))

        f = rsb.filter.OriginFilter(origin = senderId1, invert = True)
        self.assertFalse(f.match(e1))
        self.assertTrue(f.match(e2))

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(ScopeFilterTest))
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(OriginFilterTest))
    return suite
