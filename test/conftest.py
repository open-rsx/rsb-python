# ============================================================
#
# Copyright (C) 2010, 2018 by Johannes Wienke
# Copyright (C) 2012, 2014 Jan Moringen
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

import pytest

import rsb


@pytest.fixture(autouse=True)
def rsb_config_socket(tmpdir):
    conf_file = tmpdir.join('with-socket.conf')
    conf_file.write('''[introspection]
enabled = 0

[transport.inprocess]
enabled = 0

[transport.socket]
enabled = 1
port    = 55666''')
    rsb.get_default_participant_config()
    rsb.set_default_participant_config(
        rsb.ParticipantConfig.from_file(str(conf_file)))


@pytest.fixture()
def rsb_config_inprocess(tmpdir):
    conf_file = tmpdir.join('with-inprocess.conf')
    conf_file.write('''[introspection]
enabled = 0

[transport.inprocess]
enabled = 1

[transport.socket]
enabled = 0
port    = 55666''')
    rsb.get_default_participant_config()
    rsb.set_default_participant_config(
        rsb.ParticipantConfig.from_file(str(conf_file)))
