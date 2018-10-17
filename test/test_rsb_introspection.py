# ============================================================
#
# Copyright (C) 2014, 2018 Jan Moringen
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

import threading
import uuid

import pytest

import rsb
from rsb.introspection import HostInfo, ParticipantInfo, ProcessInfo


class TestParticipantInfo:

    def test_construction_without_parent_id(self):
        ParticipantInfo(kind='listener',
                        participant_id=uuid.uuid4(),
                        scope='/foo',
                        data_type=str)

    def test_construction_with_parent_id(self):
        ParticipantInfo(kind='listener',
                        participant_id=uuid.uuid4(),
                        scope='/foo',
                        data_type=str,
                        parent_id=uuid.uuid4())


class TestProcessInfo:

    def test_construction_defaults(self):
        info = ProcessInfo()
        assert isinstance(info.process_id, int)
        assert isinstance(info.rsb_version, str)


class TestHostInfo:

    def test_construction_defaults(self):
        info = HostInfo()
        assert isinstance(info.host_id, str) or info.host_id is None
        assert isinstance(info.machine_type, str)
        assert isinstance(info.software_type, str)
        assert isinstance(info.software_version, str)


class TestIntrospectionEvents:

    @pytest.mark.usefixture('rsb_config_socket')
    def test_introspection_events(self):
        # The listener must be able to deserialize introspection events. But
        # since it is created without introspection enabled, it does not force
        # the initialization of the introspection module.
        rsb._initialize_introspection()

        # Collect events in a thread-safe way and make sure the number is
        # right: one event is expected for the creation of the participant,
        # followed by one event for its destruction.
        events = []
        events_cv = threading.Condition()
        expected_events = 2

        def add_event(event):
            with events_cv:
                events.append(event)
                if len(events) == expected_events:
                    events_cv.notify()

        with rsb.create_listener(rsb.introspection.BASE_SCOPE) as listener:
            listener.add_handler(add_event)
            # Create and destroy a participant with enabled introspection. This
            # generates two introspection events.
            rsb.get_default_participant_config().introspection = True
            with rsb.create_informer('/foo'):
                pass
            with events_cv:
                events_cv.wait_for(lambda: len(events) >= expected_events,
                                   timeout=10)
        assert len(events) == expected_events
