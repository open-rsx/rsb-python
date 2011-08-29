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
    server.addMethod('echo', lambda x: x, str, str)

    # It is also possible to create a LocalServer with a given set of
    # methods. This construction avoids adding the methods
    # individually.
    server = createServer(Scope('/example/server'),
                          methods = [ ('echo2', lambda x: x, str, str) ])

    # Finally, a LocalServer can be created by exposing some or all
    # methods of an ordinary Python object.
    class MyObject:
        def echo3(self, arg):
            return arg

    server = createServer(Scope('/example/server'),
                          object = MyObject(),
                          expose = [ ('echo3', str, str) ])

    # Note: the code above creates three servers, each of which
    # provides one method on the scope /example/server

    # Wait for method calls by clients.
    sleep(100)
