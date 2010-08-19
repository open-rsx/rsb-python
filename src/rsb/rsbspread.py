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
import rsb.filter
import Notification_pb2

class SpreadPort(rsb.Port):
    
    def __init__(self, spreadModule = spread):
        self.__spreadModule = spreadModule
        self.__logger = logging.getLogger(str(self.__class__))
        self.__connection = None
        self.__uriSubscribers = {}
        """
        A map of uri subscriptions with the list of subscriptions.
        """
        
    def activate(self):
        if self.__connection == None:
            self.__logger.info("Activating spread port")
            self.__connection = self.__spreadModule.connect()
        
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

    def filterNotify(self, filter, action):
        
        if self.__connection == None:
            raise RuntimeError("SpreadPort not activated")
                
        # scope filter is the only interesting filter
        if (isinstance(filter, rsb.filter.ScopeFilter)):
            
            uri = filter.getURI()
            
            if action == rsb.filter.FilterAction.ADD:
                # join group if necessary, else only increment subscription counter
                
                if not uri in self.__uriSubscribers:
                    self.__connection.join(uri)
                    self.__uriSubscribers[uri] = 1
                    self.__logger.info("joined group '%s'" % uri)
                else:
                    self.__uriSubscribers[uri] = self.__uriSubscribers[uri] + 1

            elif action == rsb.filter.FilterAction.REMOVE:
                # leave group if no more subscriptions exist
                
                if not uri in self.__uriSubscribers:
                    self.__logger.warning("Got unsubscribe for uri '%s' eventhough I was not subscribed" % filter.getURI())
                    return
                    
                assert(self.__uriSubscribers[uri] > 0)
                self.__uriSubscribers[uri] = self.__uriSubscribers[uri] - 1
                if self.__uriSubscribers[uri] == 0:
                    self.__connection.leave(uri)
                    self.__logger.info("left group '%s'" % uri)
                    del self.__uriSubscribers[uri]

            else:
                self.__logger.warning("Received unknown filter action %s for filter %s" % (action, filter))
                
        else:
            self.__logger.debug("Ignoring filter %s with action %s" % (filter, action))
