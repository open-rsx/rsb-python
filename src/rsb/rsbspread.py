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

"""
Spread port implementation for RSB.

@author: jwienke
"""

import logging

import spread

import rsb
import Notification_pb2

class SpreadPort(rsb.Port):
    
    def __init__(self):
        self.__logger = logging.getLogger(str(self.__class__))
        self.__connection = None
        
    def activate(self):
        self.__logger.info("Activating spread port")
        self.__connection = spread.connect()
        
    def deactivate(self):
        if self.__connection != None:
            self.__logger.info("Deactivating spread port")
            self.__connection.disconnect()
            self.__connection = None
        else:
            self.__logger.warning("spread port already deactivated")
    
    def push(self, event):
        
        self.__logger.debug("Sending event: %s" % event)
        
        if self.__connection == None:
            self.__logger.warning("Port not activated")
            return
        
        # create message
        n = Notification_pb2.Notification()
        n.eid = "not set yet"
        n.uri = event.uri
        n.standalone = False
        
        serialized = n.SerializeToString()
        
        # send message
        sent = self.__connection.multicast(spread.RELIABLE_MESS, event.uri, serialized)
        if (sent > 0):
            self.__logger.debug("Message sent successfully (bytes = %i)" % sent)
        else:
            self.__logger.warning("Error sending message, status code = %s" % sent)
            
