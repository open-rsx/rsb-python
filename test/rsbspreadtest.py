# ============================================================
#
# Copyright (C) 2010 by Johannes Wienke <jwienke at techfak dot uni-bielefeld dot de>
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
import rsb.rsbspread
import rsb.filter
from threading import Condition
from rsb.rsbspread import SpreadPort
from rsb.filter import ScopeFilter, FilterAction
from rsb import RSBEvent, Publisher, Subscription, Subscriber
from rsb.transport import Router
import hashlib

class SettingReceiver(object):
    
    def __init__(self):
        self.resultEvent = None
        self.resultCondition = Condition()
    
    def __call__(self, event):
        with self.resultCondition:
            self.resultEvent = event
            self.resultCondition.notifyAll()

class SpreadPortTest(unittest.TestCase):
    
    class DummyMessage:
        pass
    
    class DummyConnection:
        
        def __init__(self):
            self.clear()
            self.__cond = Condition()
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
            self.__lastMessage = SpreadPortTest.DummyMessage()
            self.__lastMessage.groups = [group]
            self.__cond.notify()
            self.__cond.release()
    
    class DummySpread:
        
        def __init__(self):
            self.returnedConnections = []
            
        def connect(self):
            c = SpreadPortTest.DummyConnection()
            self.returnedConnections.append(c)
            return c
        
    def testActivate(self):
        
        dummySpread = SpreadPortTest.DummySpread()
        port = rsb.rsbspread.SpreadPort(spreadModule = dummySpread)
        port.activate()
        self.assertEqual(1, len(dummySpread.returnedConnections))
        
        # second activation must not do anything
        port.activate()
        self.assertEqual(1, len(dummySpread.returnedConnections))
        port.deactivate()
        
    def testDeactivate(self):
        
        dummySpread = SpreadPortTest.DummySpread()
        port = rsb.rsbspread.SpreadPort(spreadModule = dummySpread)
        port.activate()
        self.assertEqual(1, len(dummySpread.returnedConnections))
        connection = dummySpread.returnedConnections[0]
        
        port.deactivate()
        self.assertEqual(1, connection.disconnectCalls)
        
        # second activation must not do anything
        port.deactivate()
        self.assertEqual(1, connection.disconnectCalls)
        
    def testSpreadSubscription(self):
        
        dummySpread = SpreadPortTest.DummySpread()
        port = rsb.rsbspread.SpreadPort(spreadModule = dummySpread)
        port.activate()
        self.assertEqual(1, len(dummySpread.returnedConnections))
        connection = dummySpread.returnedConnections[0]
        
        s1 = "xxx"
        f1 = rsb.filter.ScopeFilter(s1)
        port.filterNotify(f1, rsb.filter.FilterAction.ADD)

        hasher = hashlib.md5()
        hasher.update(s1)
        hashed = hasher.hexdigest()[:-1]
        self.assertTrue(hashed in connection.joinCalls)
        
        connection.clear()
        
        port.filterNotify(f1, rsb.filter.FilterAction.ADD)
        self.assertEqual(0, len(connection.joinCalls))
        
        connection.clear()
        
        port.filterNotify(f1, rsb.filter.FilterAction.REMOVE)
        self.assertEqual(0, len(connection.leaveCalls))
        port.filterNotify(f1, rsb.filter.FilterAction.REMOVE)
        self.assertEqual(1, len(connection.leaveCalls))
        self.assertTrue(hashed in connection.leaveCalls)
        
        port.deactivate()
        
    def testRoundtrip(self):
        
        port = SpreadPort()
        port.activate()
            
        receiver = SettingReceiver()
        port.setObserverAction(receiver)
        
        goodUri = "good"
        filter = ScopeFilter(goodUri)
        
        port.filterNotify(filter, FilterAction.ADD)

        # first an event that we do not want        
        event = RSBEvent()
        event.uri = "notGood"
        event.data = "dummy data"
        event.type = "string"
        port.push(event)
        
        # and then a desired event
        event.uri = goodUri
        port.push(event)
        
        with receiver.resultCondition:
            receiver.resultCondition.wait(5)
               
            self.assertEqual(receiver.resultEvent, event)
            
    def testUserRoundtrip(self):
        
        inport = SpreadPort()
        outport = SpreadPort()
        
        outRouter = Router(outPort = outport)
        inRouter = Router(inPort = inport)
        
        uri = "rsb://test/it"
        publisher = Publisher(uri, outRouter, "string")
        subscriber = Subscriber(uri, inRouter)
        
        receiver = SettingReceiver()
        
        subscription = Subscription()
        subscription.appendFilter(ScopeFilter(uri))
        subscription.appendAction(receiver)
        subscriber.addSubscription(subscription)
        
        data1 = "a string to test"
        publisher.publishData(data1)
        
        with receiver.resultCondition:
            receiver.resultCondition.wait(10)
            if receiver.resultEvent == None:
                self.fail("Subscriber did not receive an event")
            self.assertEqual(receiver.resultEvent.data, data1)

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(SpreadPortTest))
    return suite
