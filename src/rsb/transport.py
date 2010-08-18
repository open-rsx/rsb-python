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

class Router:
    """
    Routers to publish and subscribe on events.
    
    @author: jwienke
    """

    def __init__(self, inType, outType):
        self.__inPort = inType()
        self.__outPort = outType()
        self.__shutdown = False
        
    def __del__(self):
        if not self.__shutdown:
            self.deactivate()

    def activate(self):
        self.__inPort.activate()
        self.__outPort.activate()
    
    def deactivate(self):
        self.__shutdown = True
        # TODO implement this
    
    def publish(self, event):
        self.__outPort.push(event)

    def subscribe(self, subscription):
        pass
    
    def unsubscribe(self, subscription):
        pass
