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

from rsb import Scope, createRemoteServer;

if __name__ == "__main__":

    # Create a RemoteServer object for the remote server at scope
    # /example/server. Method calls should complete within five
    # seconds.
    server = createRemoteServer(Scope('/example/server'), timeout = 5)

    # Call the method 'methodOne' on the remote server passing it a
    # string argument. The server's reply is returned from the call as
    # for a regular function call.
    print 'server replied: "%s"' % server.methodOne('bla')
