# ============================================================
#
# Copyright (C) 2011 Jan Moringen
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

import time

import rsb
from rsb.converter import registerGlobalConverter, getGlobalConverterMap, ProtocolBufferConverter

# Load the generated protocol buffer data holder class from the
# current directory. This would look different if the protocol buffer
# code generation was properly integrated in a build process.
#
# See the comment in SimpleImage.proto for how to manually perform the
# code generation.
import sys
sys.path.append('.')
from SimpleImage_pb2 import SimpleImage

def printData(event):
    print("Received %s object with fields:\n%s"
          % (type(event.data).__name__, str(event.data)))

if __name__ == '__main__':
    # Register a protocol buffer converter for SimpleImage:
    # The generated data holder class is
    #   SimepleImage_pb2.SimpleImage
    # The protocol buffer message is called
    #   .tutorial.protobuf_converter.SimpleImage
    converter = ProtocolBufferConverter(messageClass = SimpleImage)
    registerGlobalConverter(converter)

    print("Registered converter %s" % converter)
    print("Registered converters:\n%s " % getGlobalConverterMap(bytearray))

    # After registering one or more converters, it is currently
    # necessary to replace the default participant configuration with
    # a fresh one which takes into account the newly registered
    # converters.
    #
    # This will hopefully become unnecessary in future RSB versions.
    rsb.__defaultParticipantConfig = rsb.ParticipantConfig.fromDefaultSources()

    # Create a listener that will receive the events carrying protocol
    # buffer payloads. See the listener.py example for a more detailed
    # explanation of listener creation.
    listener = rsb.createListener(rsb.Scope("/tutorial/converter"))
    listener.addHandler(printData)

    print("Listener setup finished")

    # wait endlessly for received events
    while True:
        time.sleep(100)
