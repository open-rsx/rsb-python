# ============================================================
#
# Copyright (C) 2014, 2015, 2016, 2017 Jan Moringen
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
This package contains partial introspection functionality for RSB.

The introspection functionality is implemented in terms of RSB events
and thus built on top of "ordinary" RSB communication.

This package implements the "local introspection" (i.e. introspection
sender) part of the introspection architecture.

.. codeauthor:: jmoringe
"""

import copy
import getpass
import os
import platform
import sys
import threading
import uuid

import rsb
import rsb.converter
from rsb.protocol.introspection.Bye_pb2 import Bye
from rsb.protocol.introspection.Hello_pb2 import Hello
from rsb.util import get_logger_by_class
import rsb.version

_display_name = None

# Model


class ParticipantInfo:
    """
    Instances of this class store information about a participant.

    The participant can reside in the current process or in a remote
    process.

    .. codeauthor:: jmoringe
    """

    def __init__(self, kind, participant_id, scope, data_type, parent_id=None,
                 transport_urls=None):
        self._kind = kind
        self._id = participant_id
        self._scope = rsb.Scope.ensure_scope(scope)
        self._type = data_type
        self._parent_id = parent_id
        self._transport_urls = transport_urls or []

    @property
    def kind(self):
        """
        Return the kind of the participant.

        Examples include "listener", "informer" and "local-server".

        Returns:
            str:
                A lower-case, hyphen-separated string identifying the kind of
                participant.
        """
        return self._kind

    @property
    def participant_id(self):
        """
        Return the unique id of the participant.

        Returns:
            uuid.uuid:
                The unique id of the participant.
        """
        return self._id

    @property
    def scope(self):
        """
        Return the scope of the participant.

        Returns:
            rsb.Scope:
                The scope of the participant.
        """
        return self._scope

    @property
    def data_type(self):
        """
        Return a representation of the type of the participant, if available.

        Note that this is a temporary solution and will change in
        future versions.

        Returns:
            type or tuple:
                A representation of the type.
        """
        return self._type

    @property
    def parent_id(self):
        """
        Return the unique id of the parent participant.

        May return ``None`` if no parent participant exists.

        Returns:
            uuid.uuid or NoneType:
                ``None`` or the unique id of the participant's parent.
        """
        return self._parent_id

    @property
    def transport_urls(self):
        """
        Return list of transport URLs.

        Returns:
            list:
                List of transport URLs describing the transports used
                by the participant.
        """
        return self._transport_urls

    def __str__(self):
        return '<{} {} {} at 0x{:x}>'.format(
            type(self).__name__, self.kind, self.scope.to_string(), id(self))

    def __repr__(self):
        return str(self)


_process_start_time = None


def process_start_time():
    """
    Return the start time of the current process (or an approximation).

    Returns:
        float:
            Start time in factional seconds since UNIX epoch.
    """
    global _process_start_time

    # Used cached value, if there is one.
    if _process_start_time is not None:
        return _process_start_time

    # Try to determine the start time of the current process in a
    # platform dependent way. Since all of these methods seem kind of
    # error prone, allow failing silently and fall back to the default
    # implementation below.
    if 'linux' in sys.platform:
        try:
            import re

            with open('/proc/stat') as f:
                proc_stat_content = f.read()
            btime_entry = re.match('(?:.|\n)*btime ([0-9]+)',
                                   proc_stat_content).group(1)
            boot_time_unix_seconds = int(btime_entry)

            with open('/proc/self/stat') as f:
                self_stat_content = f.read()
            start_time_boot_jiffies = int(self_stat_content.split(' ')[21])

            _process_start_time = float(boot_time_unix_seconds) \
                + float(start_time_boot_jiffies) / 100.0
        except:  # noqa: E722 do not create an error in any case
            pass

    # Default/fallback strategy: just use the current time.
    if _process_start_time is None:
        import time
        _process_start_time = time.time()

    return _process_start_time


def program_name():
    import __main__
    if hasattr(__main__, '__file__'):
        return __main__.__file__
    else:
        return '<no script>'


class ProcessInfo:
    """
    Stores information about operating system processes.

    The stored information can describe the current process, a
    different process on the local machine or a remote process.

    .. codeauthor:: jmoringe
    """

    def __init__(self,
                 process_id=os.getpid(),
                 program_name='python{}.{} {}'.format(
                     sys.version_info.major,
                     sys.version_info.minor,
                     program_name()),
                 arguments=copy.copy(sys.argv),
                 start_time=process_start_time(),
                 executing_user=None,
                 rsb_version=rsb.version.get_version()):
        self._id = process_id
        self._program_name = program_name
        self._arguments = arguments
        self._start_time = start_time
        self._executing_user = executing_user
        if not self._executing_user:
            try:
                self._executing_user = getpass.getuser()
            except OSError:
                pass
        self._rsb_version = rsb_version

    @property
    def process_id(self):
        """
        Return the numeric id of the process.

        Returns:
            int:
                The numeric id of the process.
        """
        return self._id

    @property
    def program_name(self):
        """
        Return the name of the program being executed in the process.

        Returns:
            str:
                The name of the program.
        """
        return self._program_name

    @property
    def arguments(self):
        """
        Return the list of commandline argument to the process.

        Returns:
            list:
                A list of commandline argument strings
        """
        return self._arguments

    @property
    def start_time(self):
        """
        Return the start time of the process.

        Returns:
            float:
                start time in fractional seconds since UNIX epoch.
        """
        return self._start_time

    @property
    def executing_user(self):
        """
        Return the login- or account-name of the user executing the process.

        Returns:
            str:
                login- or account-name of the user executing the process or
                None if not determinable
        """
        return self._executing_user

    @property
    def rsb_version(self):
        """
        Return the version of the RSB implementation used in this process.

        Returns:
            str:
                Version string of the form::

                   MAJOR.MINOR.REVISION[-COMMIT]
        """
        return self._rsb_version

    def __str__(self):
        return '<{} {} [{}] at 0x{:x}>'.format(
            type(self).__name__, self.program_name, self.process_id, id(self))

    def __repr__(self):
        return str(self)


def host_id():
    """
    Return a unique id string for the current host.

    Returns:
        str or NoneType:
            A platform-dependent, string (hopefully) uniquely identifying the
            current host or ``None`` if such an id cannot be obtained.
    """
    def maybe_read(filename):
        try:
            with open(filename, 'r') as f:
                return f.read().strip()
        except:  # noqa: E722 do not create an error in any case
            return None

    return \
        ('linux' in sys.platform and maybe_read('/var/lib/dbus/machine-id')) \
        or ('linux' in sys.platform and maybe_read('/etc/machine-id')) \
        or None


def machine_type():
    result = platform.machine().lower()
    if result in ['i368', 'i586', 'i686']:
        return 'x86'
    elif result in ['x86_64', 'amd64']:
        return 'x86_64'
    else:
        return result


def machine_version():
    if 'linux' in sys.platform:
        import re

        try:
            cpu_info = open('/proc/cpuinfo').read()
            return re.match('(?:.|\n)*model name\t: ([^\n]+)',
                            cpu_info).group(1)
        except:  # noqa: E722 do not create an error in any case
            return None


class HostInfo:
    """
    Instances of this class store information about a host.

    The stored information can describe the local host or a remote
    host.

    .. codeauthor:: jmoringe
    """

    def __init__(self,
                 host_id=host_id(),
                 hostname=platform.node().split('.')[0],
                 machine_type=machine_type(),
                 machine_version=machine_version(),
                 software_type=platform.system().lower(),
                 software_version=platform.release()):
        self._id = host_id
        self._hostname = hostname
        self._machine_type = machine_type
        self._machine_version = machine_version
        self._software_type = software_type
        self._software_version = software_version

    @property
    def host_id(self):
        """
        Return the unique id string for the host.

        Returns:
            str or None:
                The platform-dependent, (hopefully) unique id string.
        """
        return self._id

    @property
    def hostname(self):
        """
        Return the hostname of the host.

        Returns:
            str:
                The hostname.
        """
        return self._hostname

    @property
    def machine_type(self):
        """
        Return the type of the machine, usually CPU architecture.

        Returns:
            str or NoneType:
                The machine type when known.
        """
        return self._machine_type

    @property
    def machine_version(self):
        """
        Return the version of the machine within its type.

        Usually the CPU identification string.

        Returns:
            str or NoneType:
                The machine version when known.
        """
        return self._machine_version

    @property
    def software_type(self):
        """
        Return the type of the operating system running on the host.

        Usually the kernel name.

        Returns:
            str or NoneType:
                The software type when known.
        """
        return self._software_type

    @property
    def software_version(self):
        """
        Return version information about the operating systems.

        Provides the version of the operating system within its type,
        usually the kernel version string.

        Returns:
            str or NoneType:
                The software version when known.
        """
        return self._software_version

    def __str__(self):
        return '<{} {} {} {} at 0x{:x}>'.format(
            type(self).__name__, self.hostname, self.machine_type,
            self.software_type, id(self))

    def __repr__(self):
        return str(self)

# IntrospectionSender


BASE_SCOPE = rsb.Scope('/__rsb/introspection/')

PARTICIPANTS_SCOPE = BASE_SCOPE.concat(rsb.Scope('/participants/'))
HOSTS_SCOPE = BASE_SCOPE.concat(rsb.Scope('/hosts/'))


def participant_scope(participant_id, base_scope=PARTICIPANTS_SCOPE):
    return base_scope.concat(rsb.Scope('/' + str(participant_id)))


def process_scope(host_id, process_id, base_scope=HOSTS_SCOPE):
    return (base_scope
            .concat(rsb.Scope('/' + host_id))
            .concat(rsb.Scope('/' + process_id)))


class IntrospectionSender:
    """
    Sends introspection information to other RSB processes.

    Instances of this class (usually zero or one per process) send
    information about participants in the current process, the current
    process itself and the local host to receivers of introspection
    information.

    Instances need to be notified of created and destroyed
    participants via calls of the :obj:`add_participant` and
    :obj:`remove_participant` methods.

    .. codeauthor:: jmoringe
    """

    def __init__(self):
        self._logger = get_logger_by_class(self.__class__)

        self._participants = []

        self._process = ProcessInfo()
        self._host = HostInfo()

        self._informer = rsb.create_informer(PARTICIPANTS_SCOPE)
        self._listener = rsb.create_listener(PARTICIPANTS_SCOPE)

        def handle(event):
            # TODO use filter when we get conjunction filter
            if event.method not in ['REQUEST', 'SURVEY']:
                return

            participant_id = None
            participant = None
            if len(event.scope.components) > \
                    len(PARTICIPANTS_SCOPE.components):
                try:
                    participant_id = uuid.UUID(event.scope.components[-1])
                    if participant_id is not None:
                        participant = next(
                            (p for p in self._participants
                             if p.participant_id == participant_id),
                            None)
                except Exception:
                    self._logger.warn('Query event %s does not '
                                      'properly address a participant',
                                      event, exc_info=True)

            def process(thunk):
                if participant is not None and event.method == 'REQUEST':
                    thunk(query=event, participant=participant)
                elif participant is None and event.method == 'SURVEY':
                    for p in self._participants:
                        thunk(query=event, participant=p)
                else:
                    self._logger.warn('Query event %s not understood', event)

            if event.data is None:
                process(self.send_hello)
            elif event.data == 'ping':
                process(self.send_pong)
            else:
                self._logger.warn('Query event %s not understood', event)

        self._listener.add_handler(handle)

        self._server = rsb.create_local_server(
            process_scope(self._host.host_id or self._host.hostname,
                          str(self._process.process_id)))

        def echo(request):
            reply = rsb.Event(scope=request.scope,
                              data=request.data,
                              data_type=type(request.data))
            reply.meta_data.set_user_time('request.send',
                                          request.meta_data.send_time)
            reply.meta_data.set_user_time('request.receive',
                                          request.meta_data.receive_time)
            return reply
        self._server.add_method('echo', echo,
                                request_type=rsb.Event,
                                reply_type=rsb.Event)

    def deactivate(self):
        self._listener.deactivate()
        self._informer.deactivate()
        self._server.deactivate()

    @property
    def process(self):
        return self._process

    @property
    def host(self):
        return self._host

    def add_participant(self, participant, parent=None):
        parent_id = None
        if parent:
            parent_id = parent.participant_id

        def camel_case_to_dash_seperated(name):
            result = []
            for i, c in enumerate(name):
                if c.isupper() and i > 0 and name[i - 1].islower():
                    result.append('-')
                result.append(c.lower())
            return ''.join(result)

        info = ParticipantInfo(
            kind=camel_case_to_dash_seperated(type(participant).__name__),
            participant_id=participant.participant_id,
            parent_id=parent_id,
            scope=participant.scope,
            data_type=object,  # TODO
            transport_urls=participant.transport_urls)

        self._participants.append(info)

        self.send_hello(info)

    def remove_participant(self, participant):
        removed = None
        for p in self._participants:
            if p.participant_id == participant.participant_id:
                removed = p
                break

        if removed is not None:
            self._participants.remove(removed)
            self.send_bye(removed)

        return bool(self._participants)

    def send_hello(self, participant, query=None):
        hello = Hello()
        hello.kind = participant.kind
        hello.id = participant.participant_id.bytes
        hello.scope = participant.scope.to_string()
        if participant.parent_id:
            hello.parent = participant.parent_id.bytes
        for url in participant.transport_urls:
            hello.transport.append(url)

        host = hello.host
        if self.host.host_id is None:
            host.id = self.host.hostname
        else:
            host.id = self.host.host_id
        host.hostname = self.host.hostname
        host.machine_type = self.host.machine_type
        if self.host.machine_version is not None:
            host.machine_version = self.host.machine_version
        host.software_type = self.host.software_type
        host.software_version = self.host.software_version

        process = hello.process
        process.id = str(self.process.process_id)
        process.program_name = self.process.program_name
        for argument in self.process.arguments:
            process.commandline_arguments.append(argument)
        process.start_time = int(self.process.start_time * 1000000.0)
        if self.process.executing_user:
            process.executing_user = self.process.executing_user
        process.rsb_version = self.process.rsb_version
        if _display_name:
            process.display_name = _display_name
        scope = participant_scope(participant.participant_id,
                                  self._informer.scope)
        hello_event = rsb.Event(scope=scope,
                                data=hello,
                                data_type=type(hello))
        if query:
            hello_event.add_cause(query.event_id)
        self._informer.publish_event(hello_event)

    def send_bye(self, participant):
        bye = Bye()
        bye.id = participant.participant_id.bytes

        scope = participant_scope(participant.participant_id,
                                  self._informer.scope)
        bye_event = rsb.Event(scope=scope,
                              data=bye,
                              data_type=type(bye))
        self._informer.publish_event(bye_event)

    def send_pong(self, participant, query=None):
        scope = participant_scope(
            participant.participant_id, self._informer.scope)
        pong_event = rsb.Event(scope=scope,
                               data='pong',
                               data_type=str)
        if query:
            pong_event.add_cause(query.event_id)
        self._informer.publish_event(pong_event)


_sender = None


def handle_participant_creation(participant, parent=None):
    """
    Notify about a created participant.

    This function is intended to be connected to
    :obj:`rsb.participant_creation_hook` and calls
    :obj:`IntrospectionSender.add_participant` when appropriate, first
    creating the :obj:`IntrospectionSender` instance, if necessary.
    """
    global _sender

    if participant.scope.is_sub_scope_of(BASE_SCOPE) \
       or not participant.config.introspection:
        return

    if _sender is None:
        _sender = IntrospectionSender()
    _sender.add_participant(participant, parent=parent)


def handle_participant_destruction(participant):
    """
    Notify about a removed participant.

    This function is intended to be connected to
    :obj:`rsb.participant_destruction_hook` and calls
    :obj:`IntrospectionSender.remove_participant` when appropriate,
    potentially deleting the :obj:`IntrospectionSender` instance
    afterwards.
    """
    global _sender

    if participant.scope.is_sub_scope_of(BASE_SCOPE) \
       or not participant.config.introspection:
        return

    if _sender and not _sender.remove_participant(participant):
        _sender.deactivate()
        _sender = None


_introspection_initialized = False
_introspection_mutex = threading.RLock()


def rsb_initialize():
    """
    Initialize the introspection module.

    Plugin hook implementation.
    """
    global _introspection_initialized
    global _display_name

    with _introspection_mutex:
        if not _introspection_initialized:
            _introspection_initialized = True

            _display_name = rsb._default_configuration_options.get(
                'introspection.displayname')

            # Register converters for introspection messages
            for clazz in [Hello, Bye]:
                converter = rsb.converter.ProtocolBufferConverter(
                    message_class=clazz)
                rsb.converter.register_global_converter(
                    converter, replace_existing=True)

            rsb.participant_creation_hook.add_handler(
                handle_participant_creation)
            rsb.participant_destruction_hook.add_handler(
                handle_participant_destruction)
