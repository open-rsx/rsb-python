# ============================================================
#
# Copyright (C) 2011, 2012 Jan Moringen
#
# This file may be licensed under the terms of the
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
# ============================================================

import logging
from time import sleep

from rsb import create_local_server, Scope

if __name__ == '__main__':
    # Pacify logger.
    logging.basicConfig()

    # Create a LocalServer object that exposes its methods under the
    # scope /example/server.
    server = create_local_server(Scope('/example/server'))

    # Add a method to the server.
    server.add_method('echo', lambda x: x, str, str)

    # It is also possible to create a LocalServer with a given set of
    # methods. This construction avoids adding the methods
    # individually.
    server = create_local_server(Scope('/example/server'),
                                 methods=[('echo2', lambda x: x, str, str)])

    # Finally, a LocalServer can be created by exposing some or all
    # methods of an ordinary Python object.
    class MyObject:
        def echo3(self, arg):
            return arg

    server = create_local_server(Scope('/example/server'),
                                 provider=MyObject(),
                                 expose=[('echo3', str, str)])

    # Note: the code above creates three servers, each of which
    # provides one method on the scope /example/server

    # Wait for method calls by clients.
    sleep(100)
