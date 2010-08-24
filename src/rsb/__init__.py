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
        #self.__type = None 

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
    
    def __str__(self):
        
        return "%s[uuid = %s, uri = '%s', data = '%s']" % ("RSBEvent", self.__uuid, self.__uri, self.__data)

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
    
class EventProcessor(object):
    """
    @author: jwienke
    """
    
    def __init__(self, numThreads = 5):
        # TODO threading!!!
        self.__pool = None
        self.__subscriptions = []
    
    def process(self, event):
        """
        Dispatches the event to all registered subscribers.
        
        @type event: RSBEvent
        @param event: event to dispatch
        """
        for sub in self.__subscriptions:
            if sub.match(event):
                for action in sub.getActions():
                    action(event)                
    
    def subscribe(self, subscription):
        """
        Subscribe on selected actions.
        
        @type subscription: Subscription
        @param subscription: the subscription to add
        """
        self.__subscriptions.append(subscription)
    
    def unsubscribe(self, subscription):
        """
        Unsubscribe.
        
        @type subscription: Subscription
        @param subscription: subscription to remove
        """
        self.__subscriptions.remove(subscription)
