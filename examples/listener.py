# ============================================================
#
# Copyright (C) 2011 by Johannes Wienke
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

# mark-start::body
import logging
import threading
import time

import rsb


_received_event = threading.Event()


def handle(event):
    print("Received event: {}".format(event))
    _received_event.set()


if __name__ == '__main__':
    # Pacify logger.
    logging.basicConfig()

    # Create a listener on the specified scope. The listener will
    # dispatch all received events asynchronously to all registered
    # handlers.
    with rsb.create_listener("/example/informer") as listener:

        # Add a handler to handle received events. Handlers are callable
        # objects with the received event as the single argument.
        listener.add_handler(handle)

        # Wait for an event to arrive and terminate afterwards
        _received_event.wait()
        # Give the informer some more time to finish for the socket transport
        time.sleep(1)
# mark-end::body
