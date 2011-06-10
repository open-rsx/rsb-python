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
from rsb import createInformer, Scope

if __name__ == '__main__':

    # create an informer for strings on scope "/example/informer".
    informer = createInformer(Scope("/example/informer"), dataType=str)
    
    print("Informer setup finished")
    
    # send some events using a method that directly accepts data
    for i in range(1200):
        informer.publishData("a test string")
        
    print("Sent events, exiting")
