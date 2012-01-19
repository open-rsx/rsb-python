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

from threading import RLock

class Bus(object):
    '''
    Singleton-like representation of the local bus.
    
    @author: jwienke
    '''
    
    def __init__(self):
        self.__mutex = RLock()
        self.__sinksByScope = {}
    
    def addSink(self, sink):
        '''
        Adds a sink for events pushed to the Bus.
        
        @param sink: the sink to add
        '''
        with self.__mutex:
            # ensure that there is a list of sinks for the given scope
            if sink.scope not in self.__sinksByScope:
                self.__sinksByScope[sink.scope] = []
            self.__sinksByScope[sink.scope].append(sink)
    
    def removeSink(self, sink):
        '''
        Removes a sink to not be notified anymore.
        
        @param sink: sink to remove
        '''
        with self.__mutex:
            # return immediately if there is no such scope known for sinks
            if sink.scope not in self.__sinksByScope:
                return
            self.__sinksByScope[sink.scope].remove(sink)
    
    def handle(self, event):
        '''
        Dispatches the provided event to all sinks of the appropriate scope.
        
        @param event: event to dispatch
        @type event: rsb.Event
        '''
        
        with self.__mutex:
            
            for scope, sinkList in self.__sinksByScope.items():
                if scope == event.scope or scope.isSuperScopeOf(event.scope):
                    for sink in sinkList:
                        sink.handle(event)

bus = Bus()
