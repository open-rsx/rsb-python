# ============================================================
#
# Copyright (C) 2011 Jan Moringen <jmoringe@techfak.uni-bielefeld.de>
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

from time import sleep

from rsb import Scope, createServer

if __name__ == '__main__':

    # Create a LocalServer object that exposes its methods under the
    # scope /example/server.
    server = createServer(Scope('/example/server'))

    # Add a method to the server.
    server.addMethod('bla', lambda x: x, str, str)

    server = createServer(Scope('/example/server'),
                          methods = [ ('bla', lambda x: x, str, str) ])

    class MyObject:
        def bla(self, arg):
            return arg

    server = createServer(Scope('/example/server'),
                          object = MyObject(),
                          expose = [ ('bla', str, str) ])

    # Wait for method calls by clients.
    sleep(100)
