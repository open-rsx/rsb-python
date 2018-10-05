# ============================================================
#
# Copyright (C) 2014 Jan Moringen
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

import unittest
import uuid

from rsb.introspection import HostInfo, ParticipantInfo, ProcessInfo


class ParticipantInfoTest(unittest.TestCase):

    def test_construction_without_parent_id(self):
        ParticipantInfo(kind='listener',
                        participant_id=uuid.uuid4(),
                        scope='/foo',
                        data_type=str)

    def test_construction_with_parent_id(self):
        ParticipantInfo(kind='listener',
                        participant_id=uuid.uuid4(),
                        scope='/foo',
                        data_type=str,
                        parent_id=uuid.uuid4())


class ProcessInfoTest(unittest.TestCase):

    def test_construction_defaults(self):
        info = ProcessInfo()
        self.assertTrue(isinstance(info.process_id, int))
        self.assertTrue(isinstance(info.rsb_version, str))


class HostInfoTest(unittest.TestCase):

    def test_construction_defaults(self):
        info = HostInfo()
        self.assertTrue(isinstance(info.host_id, str) or info.host_id is None)
        self.assertTrue(isinstance(info.machine_type, str))
        self.assertTrue(isinstance(info.software_type, str))
        self.assertTrue(isinstance(info.software_version, str))
