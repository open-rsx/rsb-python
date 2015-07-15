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
# The development of this software was supported by:
#   CoR-Lab, Research Institute for Cognition and Robotics
#     Bielefeld University
#
# ============================================================

import logging
import time

import rsb
import rsb.converter

# See ./registration.py.
import sys
sys.path.append('.')
from SimpleImage_pb2 import SimpleImage

if __name__ == '__main__':
    # Pacify logger.
    logging.basicConfig()

    # See ./registration.py
    converter = rsb.converter.ProtocolBufferConverter(messageClass=SimpleImage)
    rsb.converter.registerGlobalConverter(converter)

    rsb.setDefaultParticipantConfig(rsb.ParticipantConfig.fromDefaultSources())

    # Create a listener that will receive the events carrying protocol
    # buffer payloads. See the listener.py example for a more detailed
    # explanation of listener creation.
    with rsb.createListener(rsb.Scope("/example/converter")) as listener:
        def printData(event):
            print("Received %s object with fields:\n%s"
                  % (type(event.data).__name__, str(event.data)))
        listener.addHandler(printData)

        # wait endlessly for received events
        while True:
            time.sleep(100)
