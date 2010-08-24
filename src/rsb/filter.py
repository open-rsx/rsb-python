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

import rsb.util

FilterAction = rsb.util.Enum("FilterAction", ["ADD", "REMOVE", "UPDATE"])

class AbstractFilter(object):
    """
    Interface for concrete filters.
    
    @author: jwienke
    """
    
    def match(self, event):
        """
        Matches this filter against a given event.
        
        @type event: rsb.RSBEvent
        @param event: event to match against
        @rtype: bool
        @return: True if this filter matches the event, else False
        """
        pass

class ScopeFilter(AbstractFilter):
    """
    A filter to restrict the uri scope for events.
    
    @author: jwienke
    """
    
    def __init__(self, uri):
        """
        Constructs a new scope filter with a given uri to restrict to.
        
        @param uri: top-level uri to accept and al child scopes
        """
        self.__uri = uri
        
    def getURI(self):
        """
        Returns the top-level uri this filter matches for.
        
        @return: uri
        """
        return self.__uri

    def match(self, event):
        return event.uri == self.__uri
    
class RecordingTrueFilter(AbstractFilter):
    
    def __init__(self):
        self.events = []
        
    def match(self, event):
        self.events.append(event)
        return True
    
class RecordingFalseFilter(AbstractFilter):
    
    def __init__(self):
        self.events = []
        
    def match(self, event):
        self.events.append(event)
        return False   
    
class TrueFilter(AbstractFilter):
        def match(self, event):
            return True
        
class FalseFilter(AbstractFilter):
    def match(self, event):
        return False
        