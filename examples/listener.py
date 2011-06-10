# ============================================================
#
# Copyright (C) 2011 by Johannes Wienke <jwienke at techfak dot uni-bielefeld dot de>
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
from rsb import createListener, Scope
import time

def handle(event):
    print("Received event: %s" % event)

if __name__ == '__main__':
    
    # create a listener on the specified scope. The listener will dispatch all
    # received events asynchronously to all registered listeners
    listener = createListener(Scope("/example/informer"))
    
    # add a handler to handle received events. In python, handlers are callable
    # objects with the event as the single argument
    listener.addHandler(handle)
    
    print("Listener setup finished")
    
    # wait endlessly for received events
    while True:
        time.sleep(100)
