# ============================================================
#
# Copyright (C) 2010 by Johannes Wienke <jwienke at techfak dot uni-bielefeld dot de>
# Copyright (C) 2011 Jan Moringen <jmoringe@techfak.uni-bielefeld.de>
#
# This file may be licensed under the terms of of the
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
import uuid
import time

import rsb.rsbspread
import rsb.filter
from rsb import Event, Informer, Listener, Scope, EventId

class SettingReceiver(object):

    def __init__(self, scope):
        self.resultEvent = None
        self.resultCondition = threading.Condition()
        self.scope = scope

    def __call__(self, event):
        with self.resultCondition:
            self.resultEvent = event
            self.resultCondition.notifyAll()

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self.scope)

class SpreadConnectorTest(unittest.TestCase):

    class DummyMessage:
        pass

    class DummyConnection:

        def __init__(self):
            self.clear()
            self.__cond = threading.Condition()
            self.__lastMessage = None

        def clear(self):
            self.joinCalls = []
            self.leaveCalls = []
            self.disconnectCalls = 0

        def join(self, group):
            print("Join called with group %s" % group)
            self.joinCalls.append(group)

        def leave(self, group):
            self.leaveCalls.append(group)

        def disconnect(self):
            self.disconnectCalls = self.disconnectCalls + 1

        def receive(self):
            self.__cond.acquire()
            while self.__lastMessage == None:
                self.__cond.wait()
            msg = self.__lastMessage
            self.__lastMessage = None
            self.__cond.release()
            print("Returning message with groups: %s" % (msg.groups))
            return msg

        def multicast(self, type, group, message):
            print("Got multicast for group %s with message %s" % (group, message))
            self.__cond.acquire()
            self.__lastMessage = SpreadConnectorTest.DummyMessage()
            self.__lastMessage.groups = [group]
            self.__cond.notify()
            self.__cond.release()

    class DummySpread:

        def __init__(self):
            self.returnedConnections = []

        def connect(self, daemon=None):
            c = SpreadConnectorTest.DummyConnection()
            self.returnedConnections.append(c)
            return c

    def __getConnector(self,
                       clazz    = rsb.rsbspread.Connector,
                       module   = None,
                       activate = True):
        kwargs = {}
        if module:
            kwargs['spreadModule'] = module
        connector = clazz(converters = rsb.converter.getGlobalConverterMap(bytearray),
                          options    = rsb.getDefaultParticipantConfig().getTransport("spread").options,
                          **kwargs)
        if activate:
            connector.activate()
        return connector

    def testActivate(self):
        dummySpread = SpreadConnectorTest.DummySpread()
        connector = self.__getConnector(module = dummySpread)
        self.assertEqual(1, len(dummySpread.returnedConnections))

        # second activation must not do anything
        connector.activate()
        self.assertEqual(1, len(dummySpread.returnedConnections))
        connector.deactivate()

    def testDeactivate(self):
        dummySpread = SpreadConnectorTest.DummySpread()
        connector = self.__getConnector(module = dummySpread)
        self.assertEqual(1, len(dummySpread.returnedConnections))
        connection = dummySpread.returnedConnections[0]

        connector.deactivate()
        self.assertEqual(1, connection.disconnectCalls)

        # second activation must not do anything
        connector.deactivate()
        self.assertEqual(1, connection.disconnectCalls)

    def testSpreadSubscription(self):
        dummySpread = SpreadConnectorTest.DummySpread()
        connector = self.__getConnector(clazz  = rsb.rsbspread.InConnector,
                                        module = dummySpread)
        self.assertEqual(1, len(dummySpread.returnedConnections))
        connection = dummySpread.returnedConnections[0]

        s1 = Scope("/xxx")
        f1 = rsb.filter.ScopeFilter(s1)
        connector.filterNotify(f1, rsb.filter.FilterAction.ADD)

        hasher = hashlib.md5()
        hasher.update(s1.toString())
        hashed = hasher.hexdigest()[:-1]
        self.assertTrue(hashed in connection.joinCalls)

        connection.clear()

        connector.filterNotify(f1, rsb.filter.FilterAction.ADD)
        self.assertEqual(0, len(connection.joinCalls))

        connection.clear()

        connector.filterNotify(f1, rsb.filter.FilterAction.REMOVE)
        self.assertEqual(0, len(connection.leaveCalls))
        connector.filterNotify(f1, rsb.filter.FilterAction.REMOVE)
        self.assertEqual(1, len(connection.leaveCalls))
        self.assertTrue(hashed in connection.leaveCalls)

        connector.deactivate()

    def testRoundtrip(self):
        inconnector  = self.__getConnector(clazz = rsb.rsbspread.InConnector)
        outconnector = self.__getConnector(clazz = rsb.rsbspread.OutConnector)

        goodScope = Scope("/good")
        receiver = SettingReceiver(goodScope)
        inconnector.setObserverAction(receiver)

        filter = rsb.filter.ScopeFilter(goodScope)

        inconnector.filterNotify(filter, rsb.filter.FilterAction.ADD)

        # first an event that we do not want
        event = Event(EventId(uuid.uuid4(), 0))
        event.scope = Scope("/notGood")
        event.data = "dummy data"
        event.type = str
        event.metaData.senderId = uuid.uuid4()
        outconnector.handle(event)

        # and then a desired event
        event.scope = goodScope
        outconnector.handle(event)

        with receiver.resultCondition:
            receiver.resultCondition.wait(10)
            self.assertTrue(receiver.resultEvent)
            # ignore meta data here
            event.setMetaData(None)
            receiver.resultEvent.setMetaData(None)
            self.assertEqual(receiver.resultEvent, event)

    def testUserRoundtrip(self):
        inConnector  = self.__getConnector(clazz = rsb.rsbspread.InConnector)
        outConnector = self.__getConnector(clazz = rsb.rsbspread.OutConnector)

        outConfigurator = rsb.eventprocessing.OutRouteConfigurator(connectors = [ outConnector ])
        inConfigurator = rsb.eventprocessing.InRouteConfigurator(connectors = [ inConnector ])

        scope = Scope("/test/it")
        publisher = Informer(scope, str, configurator = outConfigurator)
        listener = Listener(scope, configurator = inConfigurator)

        receiver = SettingReceiver(scope)
        listener.addHandler(receiver)

        data1 = "a string to test"
        sentEvent = Event(EventId(uuid.uuid4(), 0))
        sentEvent.setData(data1)
        sentEvent.setType(str)
        sentEvent.setScope(scope)
        sentEvent.getMetaData().setUserInfo("test", "it")
        sentEvent.getMetaData().setUserInfo("test again", "it works?")
        sentEvent.getMetaData().setUserTime("blubb", 234234)
        sentEvent.getMetaData().setUserTime("bla", 3434343.45)
        sentEvent.addCause(EventId(uuid.uuid4(), 1323))
        sentEvent.addCause(EventId(uuid.uuid4(), 42))

        before = time.time()
        publisher.publishEvent(sentEvent)

        with receiver.resultCondition:
            receiver.resultCondition.wait(10)
            if receiver.resultEvent == None:
                self.fail("Listener did not receive an event")
            receiveTime = time.time()
            self.assertTrue(receiver.resultEvent.metaData.createTime <= receiver.resultEvent.metaData.sendTime <= receiver.resultEvent.metaData.receiveTime <= receiver.resultEvent.metaData.deliverTime)
            sentEvent.metaData.receiveTime = receiver.resultEvent.metaData.receiveTime
            sentEvent.metaData.deliverTime = receiver.resultEvent.metaData.deliverTime
            self.assertEqual(sentEvent, receiver.resultEvent)

    def testHierarchySending(self):

        sendScope = Scope("/this/is/a/test")
        superScopes = sendScope.superScopes(True)

        outConnector = self.__getConnector(clazz    = rsb.rsbspread.OutConnector,
                                           activate = False)
        outConfigurator = rsb.eventprocessing.OutRouteConfigurator(connectors = [ outConnector ])
        informer = Informer(sendScope, str, configurator = outConfigurator)

        # set up listeners on the complete hierarchy
        listeners = []
        receivers = []
        for scope in superScopes:

            inConnector = self.__getConnector(clazz    = rsb.rsbspread.InConnector,
                                              activate = False)
            inConfigurator = rsb.eventprocessing.InRouteConfigurator(connectors = [ inConnector ])

            listener = Listener(scope, configurator = inConfigurator)
            listeners.append(listener)

            receiver = SettingReceiver(scope)

            listener.addHandler(receiver)

            receivers.append(receiver)

        data = "a string to test"
        informer.publishData(data)

        for receiver in receivers:
            with receiver.resultCondition:
                receiver.resultCondition.wait(10)
                if receiver.resultEvent == None:
                    self.fail("Listener on scope %s did not receive an event" % receiver.scope)
                self.assertEqual(receiver.resultEvent.data, data)

    def testSequencing(self):
        inConnector  = self.__getConnector(clazz = rsb.rsbspread.InConnector)
        outConnector = self.__getConnector(clazz = rsb.rsbspread.OutConnector)

        goodScope = Scope("/good")
        receiver = SettingReceiver(goodScope)
        inConnector.setObserverAction(receiver)

        filter = rsb.filter.ScopeFilter(goodScope)

        inConnector.filterNotify(filter, rsb.filter.FilterAction.ADD)

        # first an event that we do not want
        event = Event(EventId(uuid.uuid4(), 0))
        event.scope = Scope("/notGood")
        event.data = "".join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for i in range(300502))
        event.type = str
        event.metaData.senderId = uuid.uuid4()
        outConnector.handle(event)

        # and then a desired event
        event.scope = goodScope
        outConnector.handle(event)

        with receiver.resultCondition:
            receiver.resultCondition.wait(10)
            if receiver.resultEvent == None:
                self.fail("Did not receive an event")
            #self.assertEqual(receiver.resultEvent, event)

    def testSendTimeAdaption(self):
        connector = self.__getConnector(clazz = rsb.rsbspread.OutConnector)

        event = Event(EventId(uuid.uuid4(), 0))
        event.scope = Scope("/notGood")
        event.data = "".join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for i in range(300502))
        event.type = str
        event.metaData.senderId = uuid.uuid4()

        before = time.time()
        connector.handle(event)
        after = time.time()

        self.assertTrue(event.getMetaData().getSendTime() >= before)
        self.assertTrue(event.getMetaData().getSendTime() <= after)

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(SpreadConnectorTest))
    return suite
