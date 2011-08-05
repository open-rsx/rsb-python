# ============================================================
#
# Copyright (C) 2011 Jan Moringen <jmoringe@techfak.uni-bielefeld.de>
#
# This program is free software; you can redistribute it
# and/or modify it under the terms of the GNU General
# Public License as published by the Free Software Foundation;
# either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# ============================================================

import rsb

from rsb.transport.converter import registerGlobalConverter, getGlobalConverterMap, ProtocolBufferConverter

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
