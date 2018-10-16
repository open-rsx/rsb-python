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

import pytest

import rsb
from rsb.converter import get_global_converter_map
from rsb.transport.socket import InPushConnector, OutConnector
from .transporttest import TransportCheck


def get_connector(clazz, scope, activate=True, server='auto'):
    options = dict(
        rsb.get_default_participant_config().get_transport('socket').options)
    options['server'] = server
    connector = clazz(
        converters=get_global_converter_map(bytes),
        options=options)
    connector.scope = scope
    if activate:
        connector.activate()
    return connector


class TestSocketTransport(TransportCheck):
    """
    Instantiation of the general transport test for the socket transport.

    This test uses a 'hack' to ensure that real socket communication is
    performed. The ``set_up`` fixture method resets a counter for each executed
    test function that is used to set diverging connector options for the
    different requests for connectors issued by the base class test functions.
    By varying the 'server' parameter, this ensures that disconnected instances
    are created and thus real network communication is performed.
    """

    @pytest.fixture(autouse=True)
    def set_up(self):
        self.counter = 0

    def get_server_arg(self):
        try:
            if self.counter == 0:
                return '1'
            else:
                return '0'
        finally:
            self.counter += 1

    def _get_in_push_connector(self, scope, activate=True):
        return get_connector(InPushConnector, scope, activate=activate,
                             server=self.get_server_arg())

    def _get_out_connector(self, scope, activate=True):
        return get_connector(OutConnector, scope, activate=activate,
                             server=self.get_server_arg())

    def _get_in_pull_connector(self, scope, activate=True):
        raise NotImplementedError()
