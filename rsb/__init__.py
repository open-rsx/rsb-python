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

import uuid
import logging
import threading
from rsb.util import getLoggerByClass, OrderedQueueDispatcherPool

class RSBEvent(object):
    '''
    Basic event class.
    
    @author: jwienke
    '''

    def __init__(self):
        """
        Constructs a new event with undefined type, empty uri and no data.
        The uuid is randomly generated.
        """

        self.__uuid = uuid.uuid1()
        self.__uri = ""
        self.__data = None
        self.__type = None

    def getUUID(self):
        """
        Returns the uri of this event.
        
        @return: uuid id of the event
        """

        return self.__uuid

    def setUUID(self, uuid):
        """
        Sets the uuid of the event.
        
        @param uuid: uuid to set
        """

        self.__uuid = uuid

    uuid = property(getUUID, setUUID)

    def getURI(self):
        """
        Returns the uri of this event.
        
        @return: uri
        """

        return self.__uri

    def setURI(self, uri):
        """
        Sets the uri of this event.
        
        @param uri: uri to set
        """

        self.__uri = uri

    uri = property(getURI, setURI)

    def getData(self):
        """
        Returns the user data of this event.
        
        @return: user data
        """

        return self.__data

    def setData(self, data):
        """
        Sets the user data of this event
        
        @param data: user data
        """

        self.__data = data

    data = property(getData, setData)

    def getType(self):
        """
        Returns the type of the user data of this event.
        
        @return: user data type
        """

        return self.__type

    def setType(self, type):
        """
        Sets the type of the user data of this event
        
        @param type: user data type
        """

        self.__type = type

    type = property(getType, setType)

    def __str__(self):

        return "%s[uuid = %s, uri = '%s', data = '%s', type = '%s']" % ("RSBEvent", self.__uuid, self.__uri, self.__data, self.__type)

class Subscription(object):
    """
    A subscription in the RSB system. A subscription can be restricted by
    actions and additional filter for the matching process.
    
    @author: jwienke
    """

    def __init__(self):
        """
        Creates a new subscription that does not match anything.
        """

        self.__filters = []
        self.__actions = []

    def appendFilter(self, filter):
        """
        Appends a filter to restrict this subscription.
        
        @param filter: filter to add
        """

        self.__filters.append(filter)

    def getFilters(self):
        """
        Returns all registered filters of this subscription.
        
        @return: list of filters
        """

        return self.__filters

    def appendAction(self, action):
        """
        Appends an action this subscription shall match on.
        
        @param action: action to append. callable with one argument, the
                       RSBEvent
        """

        if not action in self.__actions:
            self.__actions.append(action)

    def getActions(self):
        """
        Returns the list of all registered actions.
        
        @return: list of actions to execute on matches
        @rtype: list of callables accepting an RSBEvent
        """
        return self.__actions

    def match(self, event):
        """
        Matches this subscription against the provided event.
        
        @param event: event to match against
        @rtype: bool
        @return: True if the subscription accepts the event, else False
        """

        for filter in self.__filters:
            if not filter.match(event):
                return False

        return True
    
    def __str__(self):
        return "Subscription[filters = %s, actions = %s]" % (self.__filters, self.__actions)

class EventProcessor(object):
    """
    @author: jwienke
    """

    def __init__(self, numThreads=5):
        self.__logger = getLoggerByClass(self.__class__)
        self.__pool = OrderedQueueDispatcherPool(threadPoolSize=numThreads, delFunc=EventProcessor.__deliver, filterFunc=EventProcessor.__filter)
        self.__pool.start()

    def __del__(self):
        self.__pool.stop()

    @classmethod
    def __deliver(cls, subscription, event):
        for action in subscription.getActions():
            action(event)

    @classmethod
    def __filter(cls, subscription, event):
        return subscription.match(event)

    def process(self, event):
        """
        Dispatches the event to all registered subscribers.
        
        @type event: RSBEvent
        @param event: event to dispatch
        """
        self.__logger.debug("Processing event %s" % event)
        self.__pool.push(event)

    def subscribe(self, subscription):
        """
        Subscribe on selected actions.
        
        @type subscription: Subscription
        @param subscription: the subscription to add
        """
        self.__logger.debug("Subscription added %s" % subscription)
        self.__pool.registerReceiver(subscription)

    def unsubscribe(self, subscription):
        """
        Unsubscribe.
        
        @type subscription: Subscription
        @param subscription: subscription to remove
        """
        self.__logger.debug("Subscription removed %s" % subscription)
        self.__pool.unregisterReceiver(subscription)

class Publisher(object):
    """
    Event-sending part of the communication pattern.
    
    @author: jwienke
    """

    def __init__(self, uri, router, type):
        """
        Constructs a new Publisher.
        
        @param uri: uri of the publisher
        @param router: router object with open outgoing port for communication
        @param type: type identifier string
        @todo: maybe provide an automatic type identifier deduction for default
               types?
        """

        self.__logger = getLoggerByClass(self.__class__)

        self.__uri = uri
        self.__router = router
        # TODO check that type can be converted
        self.__type = type

        self.__active = False
        self.__mutex = threading.Lock()

        self.activate()

    def __del__(self):
        self.deactivate()

    def publishData(self, data):
        # TODO check activation
        self.__logger.debug("Publishing data '%s'" % data)
        event = RSBEvent()
        event.setData(data)
        event.setType(self.__type)
        self.publishEvent(event)

    def publishEvent(self, event):
        # TODO check activation
        # TODO check that type is available and suitable
        event.setURI(self.__uri)
        self.__logger.debug("Publishing event '%s'" % event)
        self.__router.publish(event)

    def activate(self):
        with self.__mutex:
            if not self.__active:
                self.__router.activate()
                self.__active = True
                self.__logger.info("Activated publisher")
            else:
                self.__logger.info("Activate called even though publisher was already active")

    def deactivate(self):
        with self.__mutex:
            if self.__active:
                self.__router.deactivate()
                self.__active = False
                self.__logger.info("Deactivated publisher")
            else:
                self.__logger.info("Deactivate called even though publisher was not active")

class Subscriber(object):
    """
    Event-receiving part of the communication pattern
    
    @author: jwienke
    """

    def __init__(self, uri, router):
        """
        Create a new subscriber for the specified uri.
        
        @todo: why the duplicated uri, also passed in using the scope filter?
        @param uri: uri to subscribe one
        @param router: router with existing inport
        """

        self.__logger = getLoggerByClass(self.__class__)

        self.__uri = uri
        self.__router = router

        self.__mutex = threading.Lock()
        self.__active = False

        self.activate()

    def __del__(self):
        self.deactivate()

    def activate(self):
        # TODO commonality with Publisher... refactor
        with self.__mutex:
            if not self.__active:
                self.__router.activate()
                self.__active = True
                self.__logger.info("Activated subscriber")
            else:
                self.__logger.info("Activate called even though subscriber was already active")

    def deactivate(self):
        with self.__mutex:
            if self.__active:
                self.__router.deactivate()
                self.__active = False
                self.__logger.info("Deactivated subscriber")
            else:
                self.__logger.info("Deactivate called even though subscriber was not active")

    def addSubscription(self, subscription):
        self.__logger.debug("New subscription %s" % subscription)
        self.__router.subscribe(subscription)

    def removeSubscription(self, subscription):
        self.__logger("Removing subscription %s" % subscription)
        self.__router.unsubscribe(subscription)
