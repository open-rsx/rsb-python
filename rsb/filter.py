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
from threading import Condition

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
    A filter to restrict the scope for events.
    
    @author: jwienke
    """

    def __init__(self, scope):
        """
        Constructs a new scope filter with a given scope to restrict to.
        
        @param scope: top-level scope to accept and al child scopes
        """
        self.__scope = scope

    def getScope(self):
        """
        Returns the top-level scope this filter matches for.
        
        @return: scope
        """
        return self.__scope

    def match(self, event):
        return event.scope == self.__scope or event.scope.isSubScopeOf(self.__scope)

class RecordingTrueFilter(AbstractFilter):

    def __init__(self):
        self.events = []
        self.condition = Condition()

    def match(self, event):
        with self.condition:
            self.events.append(event)
            self.condition.notifyAll()
            return True

class RecordingFalseFilter(AbstractFilter):

    def __init__(self):
        self.events = []
        self.condition = Condition()

    def match(self, event):
        with self.condition:
            self.events.append(event)
            self.condition.notifyAll()
            return False

class TrueFilter(AbstractFilter):
        def match(self, event):
            return True

class FalseFilter(AbstractFilter):
    def match(self, event):
        return False
