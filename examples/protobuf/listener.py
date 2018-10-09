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
import sys
import time

import rsb
import rsb.converter

# See ./registration.py.
sys.path.append('.')
from SimpleImage_pb2 import SimpleImage  # noqa: I100 path required before

if __name__ == '__main__':
    # Pacify logger.
    logging.basicConfig()

    # See ./registration.py
    converter = rsb.converter.ProtocolBufferConverter(
        message_class=SimpleImage)
    rsb.converter.register_global_converter(converter)

    rsb.set_default_participant_config(
        rsb.ParticipantConfig.from_default_sources())

    # Create a listener that will receive the events carrying protocol
    # buffer payloads. See the listener.py example for a more detailed
    # explanation of listener creation.
    with rsb.create_listener(rsb.Scope("/example/converter")) as listener:
        def print_data(event):
            print("Received {} object with fields:\n{}".format(
                type(event.data).__name__, str(event.data)))
        listener.add_handler(print_data)

        # wait endlessly for received events
        while True:
            time.sleep(100)
