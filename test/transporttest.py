# ============================================================
#
# Copyright (C) 2012 by Johannes Wienke <jwienke at techfak dot uni-bielefeld dot de>
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
from nose.tools import timed

from rsb import (Scope,
                 Event,
                 EventId,
                 createInformer,
                 createListener,
                 createReader)
import threading
import uuid
import rsb
import time
import random
import string


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


class TransportCheck(object):
    '''
    An abstract base class for ensuring interface assumptions about transports.

    .. codeauthor:: jwienke
    '''

    def _getInPushConnector(self, scope, activate=True):
        raise NotImplementedError()

    def _getInPullConnector(self, scope, activate=True):
        raise NotImplementedError()

    def _getOutConnector(self, scope, activate=True):
        raise NotImplementedError()

    def testRoundtrip(self):

        goodScope = Scope("/good")

        inconnector = self._getInPushConnector(goodScope)
        outconnector = self._getOutConnector(goodScope)

        receiver = SettingReceiver(goodScope)
        inconnector.setObserverAction(receiver)

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
            while receiver.resultEvent is None:
                receiver.resultCondition.wait(10)
            self.assertTrue(receiver.resultEvent)
            # ignore meta data here
            event.setMetaData(None)
            receiver.resultEvent.setMetaData(None)
            self.assertEqual(receiver.resultEvent, event)

        inconnector.deactivate()
        outconnector.deactivate()

    def testPullNonBlocking(self):
        try:
            inconnector = self._getInPullConnector(Scope("/somewhere"))
        except NotImplementedError:
            return

        received = inconnector.raiseEvent(False)
        self.assertIsNone(received)

        inconnector.deactivate()

    def testPullRoundtrip(self):

        goodScope = Scope("/good")

        try:
            inconnector = self._getInPullConnector(goodScope)
        except NotImplementedError:
            return
        outconnector = self._getOutConnector(goodScope)

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

        received = inconnector.raiseEvent(True)
        # ignore meta data here
        event.setMetaData(None)
        received.setMetaData(None)
        self.assertEqual(received, event)

        inconnector.deactivate()
        outconnector.deactivate()

    def testUserRoundtrip(self):
        scope = Scope("/test/it")
        inConnector = self._getInPushConnector(scope, activate=False)
        outConnector = self._getOutConnector(scope, activate=False)

        outConfigurator = rsb.eventprocessing.OutRouteConfigurator(
            connectors=[outConnector])
        inConfigurator = rsb.eventprocessing.InPushRouteConfigurator(
            connectors=[inConnector])

        publisher = createInformer(scope,
                                   dataType=str,
                                   configurator=outConfigurator)
        listener = createListener(scope, configurator=inConfigurator)

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

        publisher.publishEvent(sentEvent)

        with receiver.resultCondition:
            while receiver.resultEvent is None:
                receiver.resultCondition.wait(10)
            if receiver.resultEvent is None:
                self.fail("Listener did not receive an event")
            self.assertTrue(receiver.resultEvent.metaData.createTime <=
                            receiver.resultEvent.metaData.sendTime <=
                            receiver.resultEvent.metaData.receiveTime <=
                            receiver.resultEvent.metaData.deliverTime)
            sentEvent.metaData.receiveTime = \
                receiver.resultEvent.metaData.receiveTime
            sentEvent.metaData.deliverTime = \
                receiver.resultEvent.metaData.deliverTime
            self.assertEqual(sentEvent, receiver.resultEvent)

        listener.deactivate()
        publisher.deactivate()

    def testUserPullRoundtrip(self):
        scope = Scope("/test/it/pull")
        try:
            inConnector = self._getInPullConnector(scope, activate=False)
        except NotImplementedError:
            return
        outConnector = self._getOutConnector(scope, activate=False)

        outConfigurator = rsb.eventprocessing.OutRouteConfigurator(
            connectors=[outConnector])
        inConfigurator = rsb.eventprocessing.InPullRouteConfigurator(
            connectors=[inConnector])

        publisher = createInformer(scope,
                                   dataType=str,
                                   configurator=outConfigurator)
        reader = createReader(scope, configurator=inConfigurator)

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

        publisher.publishEvent(sentEvent)

        resultEvent = reader.read(True)
        self.assertTrue(resultEvent.metaData.createTime <=
                        resultEvent.metaData.sendTime <=
                        resultEvent.metaData.receiveTime <=
                        resultEvent.metaData.deliverTime)
        sentEvent.metaData.receiveTime = resultEvent.metaData.receiveTime
        sentEvent.metaData.deliverTime = resultEvent.metaData.deliverTime
        self.assertEqual(sentEvent, resultEvent)

        reader.deactivate()
        publisher.deactivate()

    def testHierarchySending(self):

        sendScope = Scope("/this/is/a/test")
        superScopes = sendScope.superScopes(True)

        outConnector = self._getOutConnector(sendScope, activate=False)
        outConfigurator = rsb.eventprocessing.OutRouteConfigurator(
            connectors=[outConnector])
        informer = createInformer(sendScope,
                                  dataType=str,
                                  configurator=outConfigurator)

        # set up listeners on the complete hierarchy
        listeners = []
        receivers = []
        for scope in superScopes:

            inConnector = self._getInPushConnector(scope, activate=False)
            inConfigurator = rsb.eventprocessing.InPushRouteConfigurator(
                connectors=[inConnector])

            listener = createListener(scope, configurator=inConfigurator)
            listeners.append(listener)

            receiver = SettingReceiver(scope)

            listener.addHandler(receiver)

            receivers.append(receiver)

        data = "a string to test"
        informer.publishData(data)

        for receiver in receivers:
            with receiver.resultCondition:
                while receiver.resultEvent is None:
                    receiver.resultCondition.wait(10)
                if receiver.resultEvent is None:
                    self.fail(
                        "Listener on scope %s did not receive an event"
                        % receiver.scope)
                self.assertEqual(receiver.resultEvent.data, data)

    def testSendTimeAdaption(self):
        scope = Scope("/notGood")
        connector = self._getOutConnector(scope)

        event = Event(EventId(uuid.uuid4(), 0))
        event.scope = scope
        event.data = "".join(
            random.choice(string.ascii_uppercase + string.ascii_lowercase +
                          string.digits) for i in range(300502))
        event.type = str
        event.metaData.senderId = uuid.uuid4()

        before = time.time()
        connector.handle(event)
        after = time.time()

        self.assertTrue(event.getMetaData().getSendTime() >= before)
        self.assertTrue(event.getMetaData().getSendTime() <= after)

        connector.deactivate()
