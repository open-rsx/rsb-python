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
        room = maxFragmentSize - fragment.ByteSize()
        if room < 5:
            raise ValueError, 'The event %s cannot be encoded in a notification because the serialized meta-data would not fit into a single fragment' % event
        fragmentSize = min(room - 4, remaining)
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
