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
from rsb.rsbspread import SpreadPort
from rsb.transport import Router
from rsb import Publisher, Subscriber, Subscription
from rsb.filter import ScopeFilter

def printer(data):
    print("received: %s" % data)

def roundtrip():
    
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    
    inport = SpreadPort()
    outport = SpreadPort()
    
    outRouter = Router(outPort = outport)
    inRouter = Router(inPort = inport)
    
    uri = "rsb://test/it"
    publisher = Publisher(uri, outRouter, "string")
    subscriber = Subscriber(uri, inRouter)
    
    subscription = Subscription()
    subscription.appendFilter(ScopeFilter(uri))
    subscription.appendAction(printer)
    subscriber.addSubscription(subscription)
    
    data1 = "a string to test"
    publisher.publishData(data1)
    
    publisher.deactivate()
    subscriber.deactivate()
    
    print("deactivated")

if __name__ == '__main__':
    roundtrip()