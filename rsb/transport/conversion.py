# ============================================================
#
# Copyright (C) 2011-2018 Jan Moringen
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

"""
Contains methods to convert :obj:`rsb.Event` instances to protobuf and back.

.. codeauthor:: jmoringe
.. codeauthor:: jwienke
"""

import itertools
import uuid

import rsb
from rsb.protocol.FragmentedNotification_pb2 import FragmentedNotification
from rsb.util import time_to_unix_microseconds, unix_microseconds_to_time


def notification_to_event(notification, wire_data, wire_schema, converter):
    """Build an event from a notification."""
    event = rsb.Event(
        rsb.EventId(uuid.UUID(bytes=notification.event_id.sender_id),
                    notification.event_id.sequence_number))
    event.scope = rsb.Scope(notification.scope.decode('ASCII'))
    if notification.HasField("method"):
        event.method = notification.method.decode('ASCII')
    event.data_type = converter.get_data_type()
    event.data = converter.deserialize(wire_data, wire_schema)

    # Meta data
    event.meta_data.create_time = unix_microseconds_to_time(
        notification.meta_data.create_time)
    event.meta_data.send_time = unix_microseconds_to_time(
        notification.meta_data.send_time)
    event.meta_data.set_receive_time()
    for info in notification.meta_data.user_infos:
        event.meta_data.set_user_info(info.key.decode('ASCII'),
                                      info.value.decode('ASCII'))
    for time in notification.meta_data.user_times:
        event.meta_data.set_user_time(
            time.key.decode('ASCII'),
            unix_microseconds_to_time(time.timestamp))

    # Causes
    for cause in notification.causes:
        event_id = rsb.EventId(uuid.UUID(bytes=cause.sender_id),
                               cause.sequence_number)
        event.add_cause(event_id)

    return event


def event_to_notification(
        notification, event, wire_schema, data, meta_data=True):
    # Identification information
    notification.event_id.sender_id = event.sender_id.bytes
    notification.event_id.sequence_number = event.sequence_number

    # Payload [fragment]
    notification.data = data

    # Fill meta-data
    if meta_data:
        notification.scope = event.scope.to_bytes()
        if event.method is not None:
            notification.method = event.method.encode('ASCII')
        notification.wire_schema = wire_schema.encode('ASCII')

        md = notification.meta_data
        md.create_time = time_to_unix_microseconds(event.meta_data.create_time)
        md.send_time = time_to_unix_microseconds(event.meta_data.send_time)
        for (k, v) in list(event.meta_data.user_infos.items()):
            info = md.user_infos.add()
            info.key = k.encode('ASCII')
            info.value = v.encode('ASCII')
        for (k, v) in list(event.meta_data.user_times.items()):
            time = md.user_times.add()
            time.key = k.encode('ASCII')
            time.timestamp = time_to_unix_microseconds(v)
        # Add causes
        for cause in event.causes:
            cause_id = notification.causes.add()
            cause_id.sender_id = cause.participant_id.bytes
            cause_id.sequence_number = cause.sequence_number


def event_to_notifications(event, converter, max_fragment_size):
    wire_data, wire_schema = converter.serialize(event.data)

    return event_and_wire_data_to_notifications(
        event, wire_data, wire_schema, max_fragment_size)


def event_and_wire_data_to_notifications(event, wire_data, wire_schema,
                                         max_fragment_size):
    remaining, offset, fragments = len(wire_data), 0, []
    for i in itertools.count():
        # Create fragment container
        fragment = FragmentedNotification()
        # Overwritten below if necessary
        fragment.num_data_parts = 1
        fragment.data_part = i
        fragments.append(fragment)

        # Fill notification object for data fragment
        #
        # We reserve at least 5 bytes for the payload: up to 4 bytes
        # for the field header and one byte for the payload data.
        room = max_fragment_size - fragment.ByteSize()
        if room < 5:
            raise ValueError('The event {} cannot be encoded in a '
                             'notification because the serialized meta-data '
                             'would not fit into a single fragment'.format(
                                 event))
        # allow for 4 byte field header
        fragment_size = min(room - 4, remaining)
        event_to_notification(fragment.notification, event,
                              wire_schema=wire_schema,
                              data=wire_data[offset:offset + fragment_size],
                              meta_data=(i == 0))
        offset += fragment_size
        remaining -= fragment_size

        if remaining == 0:
            break

    # Adjust fragment count in all fragments, if we actually produced
    # more than one.
    if len(fragments) > 1:
        for fragment in fragments:
            fragment.num_data_parts = len(fragments)

    return fragments
