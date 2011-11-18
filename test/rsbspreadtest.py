# ============================================================
#
# Copyright (C) 2010 by Johannes Wienke <jwienke at techfak dot uni-bielefeld dot de>
# Copyright (C) 2011 Jan Moringen <jmoringe@techfak.uni-bielefeld.de>
#
# This program is free software; you can redistribute it
# and/or modify it under the terms of the GNU General
# Public License as published by the Free Software Foundation;
# either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
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
from rsb.eventprocessing import Router

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
        connector = clazz(converterMap = rsb.transport.converter.getGlobalConverterMap(bytearray),
                          options      = rsb.getDefaultParticipantConfig().getTransport("spread").options,
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
        outconnector.push(event)

        # and then a desired event
        event.scope = goodScope
        outconnector.push(event)

        with receiver.resultCondition:
            receiver.resultCondition.wait(10)
            self.assertTrue(receiver.resultEvent)
            # ignore meta data here
            event.setMetaData(None)
            receiver.resultEvent.setMetaData(None)
            self.assertEqual(receiver.resultEvent, event)

    def testUserRoundtrip(self):
        inconnector  = self.__getConnector(clazz = rsb.rsbspread.InConnector)
        outconnector = self.__getConnector(clazz = rsb.rsbspread.OutConnector)

        outRouter = Router(outPort=outconnector)
        inRouter = Router(inPort=inconnector)

        scope = Scope("/test/it")
        publisher = Informer(scope, str, router=outRouter)
        listener = Listener(scope, router=inRouter)

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

        outconnector = self.__getConnector(clazz    = rsb.rsbspread.OutConnector,
                                           activate = False)
        outRouter = Router(outPort=outconnector)
        informer = Informer(sendScope, str, router=outRouter)

        # set up listeners on the complete hierarchy
        listeners = []
        receivers = []
        for scope in superScopes:

            inconnector = self.__getConnector(clazz    = rsb.rsbspread.InConnector,
                                              activate = False)
            inRouter = Router(inPort=inconnector)

            listener = Listener(scope, router=inRouter)
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
        event.data = "".join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for i in range(300502))
        event.type = str
        event.metaData.senderId = uuid.uuid4()
        outconnector.push(event)

        # and then a desired event
        event.scope = goodScope
        outconnector.push(event)

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
        connector.push(event)
        after = time.time()

        self.assertTrue(event.getMetaData().getSendTime() >= before)
        self.assertTrue(event.getMetaData().getSendTime() <= after)

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(SpreadConnectorTest))
    return suite
