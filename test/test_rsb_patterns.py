# ============================================================
#
# Copyright (C) 2011-2017 Jan Moringen
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

from threading import Condition

import pytest

import rsb
from rsb import ParticipantConfig

in_process_no_introspection_config = ParticipantConfig.from_dict({
    'introspection.enabled': '0',
    'transport.inprocess.enabled': '1'
})


class TestLocalServer:

    def test_construction(self):

        # Test creating a server without methods
        with rsb.create_local_server(
                '/some/scope',
                in_process_no_introspection_config) as server:
            assert server.methods == []

        with rsb.create_local_server(
                rsb.Scope('/some/scope'),
                in_process_no_introspection_config) as server:
            assert server.methods == []

        # Test creating a server with directly specified methods
        with rsb.create_local_server(
                rsb.Scope('/some/scope'),
                methods=[('foo', lambda x: x, str, str)],
                config=in_process_no_introspection_config) as server:
            assert [m.name for m in server.methods] == ['foo']

        # Test creating a server that exposes method of an existing
        # object
        class SomeClass:
            def bar(self, x):
                pass

        some_object = SomeClass()
        with rsb.create_local_server(
                rsb.Scope('/some/scope'),
                provider=some_object,
                expose=[('bar', str, None)],
                config=in_process_no_introspection_config) as server:
            assert [m.name for m in server.methods] == ['bar']

            # Cannot supply expose without object
            with pytest.raises(ValueError):
                rsb.create_local_server('/some/scope',
                                        expose=[('bar', str, None)])

            # Cannot supply these simultaneously
            with pytest.raises(ValueError):
                rsb.create_local_server(
                    '/some/scope',
                    provider=some_object,
                    expose=[('bar', str, None)],
                    methods=[('foo', lambda x: x, str, str)])


class TestRoundTrip:

    def test_round_trip(self):

        with rsb.create_local_server(
                '/roundtrip',
                methods=[('addone', lambda x: int(x + 1), int, int)],
                config=in_process_no_introspection_config):
            with rsb.create_remote_server('/roundtrip',
                                          in_process_no_introspection_config) \
                    as remote_server:

                # Call synchronously
                assert list(map(remote_server.addone, list(range(100)))) == \
                    list(range(1, 101))

                # Call synchronously with timeout
                assert [remote_server.addone(x, timeout=10)
                        for x in range(100)] == list(range(1, 101))

                # Call asynchronously
                assert [x.get()
                        for x in
                        list(map(remote_server.addone.asynchronous,
                                 list(range(100))))] == list(range(1, 101))

    def test_void_methods(self):

        with rsb.create_local_server(
                '/void', in_process_no_introspection_config) as local_server:

            def nothing(e):
                pass
            local_server.add_method("nothing", nothing, str)

            with rsb.create_remote_server(
                    '/void',
                    in_process_no_introspection_config) as remote_server:
                future = remote_server.nothing.asynchronous("test")
                future.get(1)

    def test_non_identifier_method_name(self):
        server_scope = '/non-identifier-server'
        method_name = 'non-identifier-method'
        with rsb.create_local_server(
                server_scope,
                in_process_no_introspection_config) as local_server:
            local_server.add_method(method_name, lambda x: x, str, str)

            with rsb.create_remote_server(
                    server_scope,
                    in_process_no_introspection_config) as remote_server:
                assert remote_server.get_method(method_name)('foo') == 'foo'

    def test_parallel_call_of_one_method(self):

        num_parallel_calls = 3
        running_calls = [0]
        call_lock = Condition()

        with rsb.create_local_server(
                '/takesometime',
                in_process_no_introspection_config) as local_server:

            def take_some_time(e):
                with call_lock:
                    running_calls[0] = running_calls[0] + 1
                    call_lock.notifyAll()
                with call_lock:
                    while running_calls[0] < num_parallel_calls:
                        call_lock.wait()
            local_server.add_method("take_some_time", take_some_time,
                                    str, allow_parallel_execution=True)

            with rsb.create_remote_server(
                    '/takesometime',
                    in_process_no_introspection_config) as remote_server:

                results = [
                    remote_server.take_some_time.asynchronous(
                        'call{}'.format(x))
                    for x in range(num_parallel_calls)]
                for r in results:
                    r.get(10)
