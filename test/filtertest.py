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


class OriginFilterTest(unittest.TestCase):

    def testMatch(self):
        senderId1 = uuid.uuid1()
        e1 = rsb.Event(id=rsb.EventId(participantId=senderId1,
                                      sequenceNumber=0))
        senderId2 = uuid.uuid1()
        e2 = rsb.Event(id=rsb.EventId(participantId=senderId2,
                                      sequenceNumber=1))

        f = rsb.filter.OriginFilter(origin=senderId1)
        self.assertTrue(f.match(e1))
        self.assertFalse(f.match(e2))

        f = rsb.filter.OriginFilter(origin=senderId1, invert=True)
        self.assertFalse(f.match(e1))
        self.assertTrue(f.match(e2))


class MethodFilterTest(unittest.TestCase):

    def testMatch(self):
        e1 = rsb.Event(method='foo')
        e2 = rsb.Event()

        f = rsb.filter.MethodFilter(method='foo')
        self.assertTrue(f.match(e1))
        self.assertFalse(f.match(e2))

        f = rsb.filter.MethodFilter(method='foo', invert=True)
        self.assertFalse(f.match(e1))
        self.assertTrue(f.match(e2))


def suite():
    suite = unittest.TestSuite()
    suite.addTest(
        unittest.TestLoader().loadTestsFromTestCase(ScopeFilterTest))
    suite.addTest(
        unittest.TestLoader().loadTestsFromTestCase(OriginFilterTest))
    suite.addTest(
        unittest.TestLoader().loadTestsFromTestCase(MethodFilterTest))
    return suite
