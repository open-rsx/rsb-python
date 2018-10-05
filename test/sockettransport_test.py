# ============================================================
#
# Copyright (C) 2012 Jan Moringen
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

from rsb import ParticipantConfig
from rsb.converter import get_global_converter_map
from rsb.transport.socket import InPushConnector, OutConnector
from .transporttest import TransportCheck


def get_connector(clazz, scope, activate=True):
    connector = clazz(converters=get_global_converter_map(bytes),
                      options=ParticipantConfig.from_file(
                          'test/with-socket.conf').get_transport(
                              'socket').options)
    connector.set_scope(scope)
    if activate:
        connector.activate()
    return connector


class SocketTransportTest(TransportCheck, unittest.TestCase):

    def _get_in_push_connector(self, scope, activate=True):
        return get_connector(InPushConnector, scope, activate=activate)

    def _get_out_connector(self, scope, activate=True):
        return get_connector(OutConnector, scope, activate=activate)
