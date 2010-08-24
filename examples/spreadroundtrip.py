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

from rsb.rsbspread import SpreadPort
from rsb.filter import ScopeFilter, FilterAction
from rsb import RSBEvent

import logging
import time

def testRoundtrip():
    
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    
    port = SpreadPort()
    def printAction(event):
        print("Received: %s" % event)
    port.setObserverAction(printAction)
    port.activate()
    
    goodUri = "good"
    filter = ScopeFilter(goodUri)
    
    port.filterNotify(filter, FilterAction.ADD)
    
    event = RSBEvent()
    event.setURI(goodUri)
    event.data = "dummy data"
    
    port.push(event)
    
    event.uri = "notGood"
    
    port.push(event)
    
    time.sleep(0.5)
    
    port.deactivate()

if __name__ == '__main__':
    testRoundtrip()