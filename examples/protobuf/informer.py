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

if __name__ == '__main__':
    # Pacify logger.
    logging.basicConfig()

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

    # Create an informer that will send the events carrying protocol
    # buffer payloads. See the informer.py example for a more detailed
    # explanation of informer creation.
    informer = rsb.createInformer(rsb.Scope("/tutorial/converter"),
                                  dataType = SimpleImage)

    print("Informer setup finished")

    image = SimpleImage()
    image.width  = 100
    image.height = 100
    image.data   = str('bla')
    informer.publishData(image)

    print("Send data, exiting")
