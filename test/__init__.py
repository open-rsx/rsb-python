# ============================================================
#
# Copyright (C) 2010 by Johannes Wienke <jwienke at techfak dot uni-bielefeld dot de>
# Copyright (C) 2012, 2014 Jan Moringen <jmoringe@techfak.uni-bielefeld.de>
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

from testconfig import config

import rsb


def setup_package():
    try:
        socket_port = config['socket']['port']
    except KeyError:
        socket_port = 55666
    # generate config files
    for name, socketenabled, inprocessenabled in \
            [('socket', '1', '0'),
             ('inprocess', '0', '1')]:
        with open('test/with-{}.conf'.format(name), 'w') as f:
            f.write('''[introspection]
enabled = 0

[transport.inprocess]
enabled = {inprocessenabled}

[transport.socket]
enabled = {socketenabled}
port    = {socketport}'''
                    .format(inprocessenabled=inprocessenabled,
                            socketenabled=socketenabled,
                            socketport=socket_port))

    # initialize participant config
    rsb.get_default_participant_config()
    rsb.set_default_participant_config(
        rsb.ParticipantConfig.from_file('test/with-inprocess.conf'))
