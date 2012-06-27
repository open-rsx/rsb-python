# ============================================================
#
# Copyright (C) 2010 by Johannes Wienke <jwienke at techfak dot uni-bielefeld dot de>
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

"""
Contains filters which can be used to restrict the amount of events received by
clients.

@author: jwienke
@author: jmoringe
"""

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

class OriginFilter (AbstractFilter):
    """
    Matching events have to originate at a particular participant.

    @author: jmoringe
    """

    def __init__(self, origin, invert = False):
        """
        @param origin: The id of the L{Participant} from which
                       matching events should originate.
        @param invert: Controls whether matching results should
                       inverted (i.e. matching events B{not}
                       originating form B{origin}).
        @type invert: bool
        """
        self.__origin = origin
        self.__invert = invert

    def getOrigin(self):
        return self.__origin

    origin = property(getOrigin)

    def getInvert(self):
        return self.__invert

    invert = property(getInvert)

    def match(self, event):
        result = self.origin == event.senderId
        if self.invert:
            return not result
        else:
            return result

    def __str__(self):
        inverted = ''
        if self.invert:
            inverted = 'not '
        return '<%s %sfrom %s at 0x%x>' % (type(self).__name__,
                                           inverted,
                                           self.origin,
                                           id(self))

    def __repr__(self):
        return '%s("%s", invert = %s)' \
            % (type(self).__name__, self.origin, self.invert)

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
