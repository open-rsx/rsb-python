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

import spread

import rsb
import Notification_pb2

class SpreadPort(rsb.Port):
    
    def __init__(self):
        self.__connection = None
        
    def activate(self):
        self.__connection = spread.connect()
    
    def push(self, event):
        # TODO convert data for sending
        n = Notification_pb2.Notification()
        n.eid = "not set yet"
        n.uri = event.uri
        n.standalone = False
        
        serialized = n.SerializeToString()
        print(serialized)
