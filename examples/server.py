# ============================================================
#
# Copyright (C) 2011, 2012 Jan Moringen <jmoringe@techfak.uni-bielefeld.de>
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
# The development of this software was supported by:
#   CoR-Lab, Research Institute for Cognition and Robotics
#     Bielefeld University
#
# ============================================================

import logging
from time import sleep

from rsb import Scope, createServer

if __name__ == '__main__':
    # Pacify logger.
    logging.basicConfig()

    # Create a LocalServer object that exposes its methods under the
    # scope /example/server.
    server = createServer(Scope('/example/server'))

    # Create a function which processes requests and returns a
    # result. Note that the name of the function does not determine
    # the name of the exposed method. See addMethod below.
    def echo(x):
        return x

    # Add the function to the server under the name "echo" .
    server.addMethod('echo', echo, str, str)

    # Wait for method calls by clients.
    sleep(100)
