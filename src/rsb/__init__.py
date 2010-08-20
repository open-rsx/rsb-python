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

class RSBEvent:
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

class Subscription:
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
        
        @param action: action to append
        """
        
        if not action in self.__actions:
            self.__actions.append(action)
            
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

class Port:
    """
    Interface for transport-specific p;orts.
    
    @author: jwienke
    """
    
    def activate(self):
        pass
    def deactivate(self):
        pass
    def publish(self, event):
        pass
    def filterNotify(self, filter, action):
        pass
    
    def setObserverAction(self, observerAction):
        """
        Sets the action used by the port to notify about incomming events.
        The call to this method must be thread-safe.
        
        @param observerAction: action called if a new message is received from
                               the port. Must accept an RSBEvent as parameter.
        """
        pass
