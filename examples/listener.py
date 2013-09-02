# ============================================================
#
# Copyright (C) 2011 by Johannes Wienke <jwienke at techfak dot uni-bielefeld dot de>
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

# mark-start::body
import time
import logging

import rsb

def handle(event):
    print("Received event: %s" % event)

if __name__ == '__main__':
    # Pacify logger.
    logging.basicConfig()

    # Create a listener on the specified scope. The listener will
    # dispatch all received events asynchronously to all registered
    # handlers.
    with rsb.createListener("/example/informer") as listener:

        # Add a handler to handle received events. Handlers are callable
        # objects with the received event as the single argument.
        listener.addHandler(handle)

        # Wait for events; clean up when interrupted.
        while True:
            time.sleep(1)
# mark-end::body
