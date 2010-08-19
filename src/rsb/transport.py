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
import logging

class Router:
    """
    Routers to publish and subscribe on events.
    
    @author: jwienke
    """

    def __init__(self, inPort, outPort):
        """
        Creates a new router.
        
        @param inPort: port for ingoing communication
        @param outPort: port for outgoing communication
        """
        
        self.__logger = logging.getLogger(str(self.__class__))
        self.__inPort = inPort
        self.__outPort = outPort
        self.__active = False
        
    def __del__(self):
        if self.__active:
            self.deactivate()

    def activate(self):
        if not self.__active:
            self.__logger.info("Activating router")
            self.__inPort.activate()
            self.__outPort.activate()
            self.__active = True
        else:
            self.__logger.warning("Router was already activated")
    
    def deactivate(self):
        if self.__active:
            self.__logger.info("Deactivating router")
            self.__inPort.deactivate()
            self.__outPort.deactivate()
            self.__active = False
        else:
            self.__logger.warning("Router was not active")
    
    def publish(self, event):
        if self.__active:
            self.__logger.debug("Publishing event: %s" % event)
            self.__outPort.push(event)
        else:
            self.__logger.warning("Router is not active. Cannot publish.")

    def subscribe(self, subscription):
        pass
    
    def unsubscribe(self, subscription):
        pass
