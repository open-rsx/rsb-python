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
import rsb

class ScopeFilterTest(unittest.TestCase):

    def testMatch(self):

        uri = "rsb:/bla"
        f = rsb.filter.ScopeFilter(uri)
        self.assertEqual(uri, f.getURI())

        e = rsb.RSBEvent()
        e.uri = uri
        self.assertTrue(f.match(e))

        e.uri = "blubbbbbb"
        self.assertFalse(f.match(e))

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(ScopeFilterTest))
    return suite

