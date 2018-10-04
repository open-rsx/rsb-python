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

# mark-start::body
import logging

import rsb
import rsb.converter

# See ./registration.py.
import sys
sys.path.append('.')
from SimpleImage_pb2 import SimpleImage

if __name__ == '__main__':
    # Pacify logger.
    logging.basicConfig()

    # See ./registration.py.
    converter = rsb.converter.ProtocolBufferConverter(
        message_class=SimpleImage)
    rsb.converter.register_global_converter(converter)

    rsb.set_default_participant_config(
        rsb.ParticipantConfig.from_default_sources())

    # Create an informer that will send the events carrying protocol
    # buffer payloads. See the informer.py example for a more detailed
    # explanation of informer creation.
    with rsb.create_informer("/example/converter",
                             data_type=SimpleImage) as informer:

        image = SimpleImage()
        image.width = 100
        image.height = 100
        image.data = str('bla')
        informer.publish_data(image)
# mark-end::body
