# ============================================================
#
# Copyright (C) 2017 by Johannes Wienke
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
import time

import rsb


if __name__ == '__main__':
    # Pacify logger.
    logging.basicConfig()

    # Create a reader on the specified scope.
    with rsb.create_reader("/example/informer") as reader:

        # Wait for the event and print it
        event = reader.read()
        print("Received event: {}".format(event))
        # Give the informer some more time to finish for the socket transport
        time.sleep(1)
# mark-end::body
