# ============================================================
#
# Copyright (C) 2010 by Johannes Wienke <jwienke at techfak dot uni-bielefeld dot de>
# Copyright (C) 2011-2018 Jan Moringen <jmoringe@techfak.uni-bielefeld.de>
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

import threading
import hashlib
import random
import string
import subprocess
import time
import uuid

from distutils.spawn import find_executable

from testconfig import config

from rsb.transport import rsbspread
from rsb import Event, Scope, EventId, ParticipantConfig
from test.transporttest import SettingReceiver, TransportCheck
import rsb

_spreadProcess = None


def setup_module():
    # pylint: disable=global-statement
    global _spreadProcess

    try:
        spread = config['spread']['daemon']
    except KeyError:
        spread = find_executable('spread')
    assert spread, 'Spread executable not found. Is it on PATH? ' \
        'Or specify it via the nose test config ' \
        'as daemon in the [spread] section.'
    _spreadProcess = subprocess.Popen([spread,
                                       '-n', 'localhost',
                                       '-c', 'test/spread.conf'])
    time.sleep(5)
    assert _spreadProcess.poll() is None, 'Spread could not be started'


def teardown_module():
    _spreadProcess.terminate()
    _spreadProcess.wait()


def getConnector(scope,
                 clazz=rsbspread.Connector,
                 module=None,
                 activate=True):
    kwargs = {}
    if module:
        kwargs['spreadModule'] = module
    options = ParticipantConfig.fromFile(
        'test/with-spread.conf').getTransport("spread").options
    daemon = '{port}@{host}'.format(port=options['port'],
                                    host=options.get('host', 'localhost'))
    connection = rsbspread.SpreadConnection(daemon, **kwargs)
    bus = rsbspread.Bus(connection)
    bus.activate()
    connector = clazz(bus=bus,
                      converters=rsb.converter.getGlobalConverterMap(
                          bytearray))
    connector.setScope(scope)
    if activate:
        connector.activate()
    return connector


class SpreadConnectorTest(unittest.TestCase):

    class DummyMessage(object):
        def __init__(self):
            self.msg_type = 42

    class DummyConnection(object):

        def __init__(self):
            self.clear()
            self.__cond = threading.Condition()
            self.__lastMessage = None

        def clear(self):
            self.joinCalls = []
            self.leaveCalls = []
            self.disconnectCalls = 0

        def join(self, group):
            self.joinCalls.append(group)

        def leave(self, group):
            self.leaveCalls.append(group)

        def disconnect(self):
            self.disconnectCalls = self.disconnectCalls + 1

        def receive(self):
            self.__cond.acquire()
            while self.__lastMessage is None:
                self.__cond.wait()
            msg = self.__lastMessage
            self.__lastMessage = None
            self.__cond.release()
            return msg

        def multicast(self, type, group, message):
            self.__cond.acquire()
            self.__lastMessage = SpreadConnectorTest.DummyMessage()
            self.__lastMessage.groups = [group]
            self.__cond.notify()
            self.__cond.release()

    class DummySpread(object):

        def __init__(self):
            self.returnedConnections = []

        def connect(self, daemon=None):
            c = SpreadConnectorTest.DummyConnection()
            self.returnedConnections.append(c)
            return c

    def testActivate(self):
        dummySpread = SpreadConnectorTest.DummySpread()
        connector = getConnector(Scope("/foo"), module=dummySpread)
        self.assertEqual(1, len(dummySpread.returnedConnections))
        connector.deactivate()

    def testDeactivate(self):
        dummySpread = SpreadConnectorTest.DummySpread()
        connector = getConnector(Scope("/foo"), module=dummySpread)
        self.assertEqual(1, len(dummySpread.returnedConnections))
        connection = dummySpread.returnedConnections[0]

        connector.deactivate()
        self.assertEqual(1, connection.disconnectCalls)

    def testSpreadSubscription(self):
        s1 = Scope("/xxx")
        dummySpread = SpreadConnectorTest.DummySpread()
        connector = getConnector(s1,
                                 clazz=rsbspread.InPushConnector,
                                 module=dummySpread)
        self.assertEqual(1, len(dummySpread.returnedConnections))
        connection = dummySpread.returnedConnections[0]

        hasher = hashlib.md5()
        hasher.update(s1.toString())
        hashed = hasher.hexdigest()[:-1]
        self.assertTrue(hashed in connection.joinCalls)

        connector.deactivate()

    def testSequencing(self):
        goodScope = Scope("/good")
        inConnector = getConnector(goodScope, clazz=rsbspread.InPushConnector)
        outConnector = getConnector(goodScope, clazz=rsbspread.OutConnector)

        try:
            receiver = SettingReceiver(goodScope)
            inConnector.setObserverAction(receiver)

            # first an event that we do not want
            event = Event(EventId(uuid.uuid4(), 0))
            event.scope = Scope("/notGood")
            event.data = "".join(random.choice(
                string.ascii_uppercase + string.ascii_lowercase + string.digits)
                for i in range(300502))
            event.type = str
            event.metaData.senderId = uuid.uuid4()
            outConnector.handle(event)

            # and then a desired event
            event.scope = goodScope
            outConnector.handle(event)

            with receiver.resultCondition:
                receiver.resultCondition.wait(10)
                if receiver.resultEvent is None:
                    self.fail("Did not receive an event")
                # self.assertEqual(receiver.resultEvent, event)
        finally:
            inConnector.deactivate()
            outConnector.deactivate()


class SpreadTransportTest(TransportCheck, unittest.TestCase):

    def _getInPushConnector(self, scope, activate=True):
        return getConnector(scope, clazz=rsbspread.InPushConnector,
                            activate=activate)

    def _getInPullConnector(self, scope, activate=True):
        return getConnector(scope, clazz=rsbspread.InPullConnector,
                            activate=activate)

    def _getOutConnector(self, scope, activate=True):
        return getConnector(scope, clazz=rsbspread.OutConnector,
                            activate=activate)
