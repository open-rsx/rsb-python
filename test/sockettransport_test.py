# ============================================================
#
# Copyright (C) 2012 Jan Moringen <jmoringe@techfak.uni-bielefeld.de>
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

from rsb import ParticipantConfig
from rsb.converter import getGlobalConverterMap
from rsb.transport.socket import OutConnector, InPushConnector

from test.transporttest import TransportCheck


def getConnector(clazz, scope, activate=True):
    connector = clazz(converters=getGlobalConverterMap(bytearray),
                      options=ParticipantConfig.fromFile(
                          'test/with-socket.conf').getTransport(
                              'socket').options)
    connector.setScope(scope)
    if activate:
        connector.activate()
    return connector


class SocketTransportTest(TransportCheck, unittest.TestCase):

    def _getInConnector(self, scope, activate=True):
        return getConnector(InPushConnector, scope, activate=activate)

    def _getOutConnector(self, scope, activate=True):
        return getConnector(OutConnector, scope, activate=activate)
