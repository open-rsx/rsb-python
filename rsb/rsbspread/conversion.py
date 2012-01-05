# ============================================================
#
# Copyright (C) 2011 Jan Moringen <jmoringe@techfak.uni-bielefeld.de>
#
# This file may be licensed under the terms of of the
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

import itertools
import uuid

import rsb
from rsb.util import unixMicrosecondsToTime, timeToUnixMicroseconds

from rsb.protocol.EventId_pb2 import EventId
from rsb.protocol.EventMetaData_pb2 import UserInfo, UserTime
from rsb.protocol.Notification_pb2 import Notification
from rsb.protocol.FragmentedNotification_pb2 import FragmentedNotification

def notificationToEvent(notification, wireData, wireSchema, converter):
    # Build event from notification
    event = rsb.Event(rsb.EventId(uuid.UUID(bytes=notification.event_id.sender_id),
                                  notification.event_id.sequence_number))
    event.scope = rsb.Scope(notification.scope)
    if notification.HasField("method"):
        event.method = notification.method
    event.type = converter.getDataType()
    event.data = converter.deserialize(wireData, wireSchema)

    # Meta data
    event.metaData.createTime = unixMicrosecondsToTime(notification.meta_data.create_time)
    event.metaData.sendTime = unixMicrosecondsToTime(notification.meta_data.send_time)
    event.metaData.setReceiveTime()
    for info in notification.meta_data.user_infos:
        event.metaData.setUserInfo(info.key, info.value)
    for time in notification.meta_data.user_times:
        event.metaData.setUserTime(time.key, unixMicrosecondsToTime(time.timestamp))

    # Causes
    for cause in notification.causes:
        id = rsb.EventId(uuid.UUID(bytes=cause.sender_id), cause.sequence_number)
        event.addCause(id)

    return event

def eventToNotifications(event, converter, maxFragmentSize):
    wireData, wireSchema = converter.serialize(event.data)

    remaining, offset, fragments = len(wireData), 0, []
    for i in itertools.count():
        # Create fragment container
        fragment = FragmentedNotification()
        fragment.num_data_parts = 1 # Overwritten below if necessary
        fragment.data_part      = i
        fragments.append(fragment)

        # Retrieve notification object
        n = fragment.notification
        n.event_id.sender_id = event.senderId.bytes
        n.event_id.sequence_number = event.sequenceNumber

        # Added meta-data if initial fragment
        if i == 0:
            n.scope = event.scope.toString()
            if not event.method is None:
                n.method = event.method
            n.wire_schema = wireSchema

            # Fill meta-data
            md = n.meta_data
            md.create_time = timeToUnixMicroseconds(event.metaData.createTime)
            md.send_time = timeToUnixMicroseconds(event.metaData.sendTime)
            for (k, v) in event.metaData.userInfos.items():
                info = md.user_infos.add()
                info.key = k
                info.value = v
            for (k, v) in event.metaData.userTimes.items():
                time = md.user_times.add()
                time.key       = k
                time.timestamp = timeToUnixMicroseconds(v)
            # Add causes
            for cause in event.causes:
                id = n.causes.add()
                id.sender_id       = cause.participantId.bytes
                id.sequence_number = cause.sequenceNumber

        # Add data fragment
        # We reserve at least 5 bytes for the payload: up to 4 bytes
        # for the field header and one byte for the payload data.
        room = maxFragmentSize - fragment.ByteSize()
        if room < 5:
            raise ValueError, 'The event %s cannot be encoded in a notification because the serialized meta-data would not fit into a single fragment' % event
        fragmentSize = min(room - 4, remaining) # allow for 4 byte field header
        n.data    =  str(wireData[offset:offset + fragmentSize])
        offset    += fragmentSize
        remaining -= fragmentSize

        if remaining == 0:
            break

    # Adjust fragment count in all fragments, if we actually produced
    # more than one.
    if len(fragments) > 1:
        for fragment in fragments:
            fragment.num_data_parts = len(fragments)

    return fragments
