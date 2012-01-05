# ============================================================
#
# Copyright (C) 2011 Jan Moringen <jmoringe@techfak.uni-bielefeld.de>
#
# This file may be licensed under the terms of of the
# GNU Lesser General Public License Version 3 (the ``LGPL''),
# or (at your option) any later version.
#
# Software distributed under the License is distributed
# on an ``AS IS'' basis, WITHOUT WARRANTY OF ANY KIND, either
# express or implied. See the LGPL for the specific language
# governing rights and limitations.
#
# You should have received a copy of the LGPL along with this
# program. If not, go to http://www.gnu.org/licenses/lgpl.html
# or write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# The development of this software was supported by:
#   CoR-Lab, Research Institute for Cognition and Robotics
#     Bielefeld University
#
# ============================================================

from rsb import Scope, createRemoteServer;

if __name__ == "__main__":

    # Create a RemoteServer object for the remote server at scope
    # /example/server. Method calls should complete within five
    # seconds.
    server = createRemoteServer(Scope('/example/server'))

    # Call the method 'methodOne' on the remote server passing it a
    # string argument. The server's reply is returned from the call as
    # for a regular function call.
    print 'server replied to synchronous call: "%s"' % server.echo('bla')

    # Call the method 'methodOne' again, this time asynchronously.
    future = server.echo.async('bla')
    # do other things
    print 'server replied to asynchronous call: "%s"' % future.get(timeout = 10)
