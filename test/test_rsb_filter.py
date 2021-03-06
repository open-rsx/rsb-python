# ============================================================
#
# Copyright (C) 2010 by Johannes Wienke
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
# ============================================================

import uuid

import rsb
from rsb import Scope
import rsb.filter


class TestScopeFilter:

    def test_match(self):

        scope = Scope("/bla")
        f = rsb.filter.ScopeFilter(scope)
        assert scope == f.scope

        e = rsb.Event()
        e.scope = scope
        assert f.match(e)
        e.scope = scope.concat(Scope("/sub/scope"))
        assert f.match(e)

        e.scope = Scope("/blubbbbbb")
        assert not f.match(e)


class TestOriginFilter:

    def test_match(self):
        sender_id1 = uuid.uuid1()
        e1 = rsb.Event(event_id=rsb.EventId(participant_id=sender_id1,
                                            sequence_number=0))
        sender_id2 = uuid.uuid1()
        e2 = rsb.Event(event_id=rsb.EventId(participant_id=sender_id2,
                                            sequence_number=1))

        f = rsb.filter.OriginFilter(origin=sender_id1)
        assert f.match(e1)
        assert not f.match(e2)

        f = rsb.filter.OriginFilter(origin=sender_id1, invert=True)
        assert not f.match(e1)
        assert f.match(e2)


class TestCauseFilter:

    def test_match(self):
        id1 = rsb.EventId(participant_id=uuid.uuid1(), sequence_number=0)
        e1 = rsb.Event(causes=[id1])
        id2 = rsb.EventId(participant_id=uuid.uuid1(), sequence_number=1)
        e2 = rsb.Event(causes=[id2])

        f = rsb.filter.CauseFilter(cause=id1)
        assert f.match(e1)
        assert not f.match(e2)

        f = rsb.filter.CauseFilter(cause=id1, invert=True)
        assert not f.match(e1)
        assert f.match(e2)


class TestMethodFilter:

    def test_match(self):
        e1 = rsb.Event(method='foo')
        e2 = rsb.Event()

        f = rsb.filter.MethodFilter(method='foo')
        assert f.match(e1)
        assert not f.match(e2)

        f = rsb.filter.MethodFilter(method='foo', invert=True)
        assert not f.match(e1)
        assert f.match(e2)
