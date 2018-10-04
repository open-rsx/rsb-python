# ============================================================
#
# Copyright (C) 2012, 2013 Jan Moringen <jmoringe@techfak.uni-bielefeld.de>
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
import logging
import sys

import rsb
import rsb.converter

# Load the generated protocol buffer data holder class from the
# current directory. This would look different if the protocol buffer
# code generation was properly integrated in a build process.
#
# See the comment in SimpleImage.proto for how to manually perform the
# code generation.
sys.path.append('.')
from SimpleImage_pb2 import SimpleImage  # noqa: I100 adding to path is
                                         #       required before

if __name__ == '__main__':
    # Pacify logger.
    logging.basicConfig()

    # Register a protocol buffer converter for SimpleImage:
    # The generated data holder class is
    #   SimepleImage_pb2.SimpleImage
    # The protocol buffer message is called
    #   .tutorial.protobuf_converter.SimpleImage
    converter = rsb.converter.ProtocolBufferConverter(
        message_class=SimpleImage)
    rsb.converter.register_global_converter(converter)

    print("Registered converter %s" % converter)
    print("Registered converters:\n%s "
          % rsb.converter.get_global_converter_map(bytes))
# mark-end::body
