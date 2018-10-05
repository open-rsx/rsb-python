# ============================================================
#
# Copyright (C) 2010 by Johannes Wienke
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
Contains the high-level user interface of RSB.

This package contains all classes that form the high-level user interface of
the RSB python implementation. It is the entry point for most users and only in
advanced cases client programs need to use classes from other modules.

In order to create basic objects have a look at the functions
:obj:`create_informer`, :obj:`create_listener`, :obj:`create_server` and
:obj:`create_remote_server`.

.. codeauthor:: jwienke
.. codeauthor:: jmoringe
"""

import configparser
import copy
from functools import reduce
import logging
import os
import platform
import re
import threading
import time
import uuid

import rsb.eventprocessing
from rsb.util import Enum, get_logger_by_class


_logger = logging.getLogger('rsb')


# prevent logging warnings about missing handlers as per:
# https://docs.python.org/2.6/library/logging.html#configuring-logging-for-a-library
# do so before importing anything from RSB itself, which might already log
# stuff
class _NullHandler(logging.Handler):
    """Null logging handler to prevent warning messages."""

    def emit(self, record):
        pass


_logger.addHandler(_NullHandler())


__default_transports_registered = False
__transport_registration_lock = threading.RLock()


def _register_default_transports():
    """Register all available transports."""
    global __default_transports_registered
    with __transport_registration_lock:
        if __default_transports_registered:
            return
        __default_transports_registered = True
        import rsb.transport.local as local
        local.initialize()
        import rsb.transport.socket as socket
        socket.initialize()


class QualityOfServiceSpec(object):
    """
    Specification of desired quality of service settings event transmission.

    Specification given here are required "at least". This means concrete
    connector implementations can provide "better" QoS specs without any
    notification to the clients. Better is decided by the integer value of the
    specification enums. Higher values mean better services.

    .. codeauthor:: jwienke
    """

    Ordering = Enum("Ordering", ["UNORDERED", "ORDERED"], [10, 20])
    Reliability = Enum("Reliability", ["UNRELIABLE", "RELIABLE"], [10, 20])

    def __init__(self, ordering=Ordering.UNORDERED,
                 reliability=Reliability.RELIABLE):
        """
        Construct a new QoS specification with desired details.

        Defaults are unordered but reliable.

        Args:
            ordering:
                desired ordering type
            reliability:
                desired reliability type
        """
        self.__ordering = ordering
        self.__reliability = reliability

    def get_ordering(self):
        """
        Return the desired ordering settings.

        Returns:
            ordering settings
        """

        return self.__ordering

    def set_ordering(self, ordering):
        """
        Set the desired ordering settings.

        Args:
            ordering: ordering to set
        """

        self.__ordering = ordering

    ordering = property(get_ordering, set_ordering)

    def get_reliability(self):
        """
        Return the desired reliability settings.

        Returns:
            reliability settings
        """

        return self.__reliability

    def set_reliability(self, reliability):
        """
        Set the desired reliability settings.

        Args:
            reliability: reliability to set
        """

        self.__reliability = reliability

    reliability = property(get_reliability, set_reliability)

    def __eq__(self, other):
        try:
            return other.__reliability == self.__reliability \
                and other.__ordering == self.__ordering
        except (AttributeError, TypeError):
            return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return "%s(%r, %r)" % (self.__class__.__name__,
                               self.__ordering,
                               self.__reliability)


CONFIG_DEBUG_VARIABLE = 'RSB_CONFIG_DEBUG'

CONFIG_FILES_VARIABLE = 'RSB_CONFIG_FILES'

CONFIG_FILE_KEY_SYSTEM = '%system'
CONFIG_FILE_KEY_PREFIX = '%prefix'
CONFIG_FILE_KEY_USER = '%user'
CONFIG_FILE_KEY_PWD = '%pwd'

DEFAULT_CONFIG_FILES = [CONFIG_FILE_KEY_SYSTEM,
                        CONFIG_FILE_KEY_PREFIX,
                        CONFIG_FILE_KEY_USER,
                        CONFIG_FILE_KEY_PWD]


def _config_file_to_dict(path, defaults=None):
    parser = configparser.RawConfigParser()
    parser.read(path)
    if defaults is None:
        options = {}
    else:
        options = defaults
    for section in parser.sections():
        for (k, v) in parser.items(section):
            options[section + '.' + k] = v.split('#')[0].strip()
    return options


def _config_environment_to_dict(defaults=None, debug=False):
    if defaults is None:
        options = {}
    else:
        options = defaults
    empty = True
    for (key, value) in list(os.environ.items()):
        if key.startswith('RSB_'):
            if debug:
                empty = False
                print(('     %s -> %s' % (key, value)))
            if not key == CONFIG_FILES_VARIABLE and value == '':
                raise ValueError('The value of the environment variable '
                                 '%s is the empty string' % key)
            options[key[4:].lower().replace('_', '.')] = value
    if debug and empty:
        print('     <none>')
    return options


def _config_default_config_files():
    if CONFIG_FILES_VARIABLE in os.environ:
        return [f for f in os.environ[CONFIG_FILES_VARIABLE].split(':') if f]
    else:
        return DEFAULT_CONFIG_FILES


def _config_default_sources_to_dict(defaults=None,
                                    files=_config_default_config_files()):
    r"""
    Return a dictionary of configuration options from a cascade of sources.

    Obtain configuration options from multiple sources, store them
    in a :obj:`ParticipantConfig` object and return it. By default,
    the following sources of configuration information will be
    consulted:

     1. ``/etc/rsb.conf``
     2. ``$prefix/etc/rsb.conf``
     3. ``~/.config/rsb.conf``
     4. ``\$(PWD)/rsb.conf``
     5. Environment Variables

    Args:
        defaults (dict of str -> str):
            dictionary with default options
        files (list of str)
            filenames and placeholders for configuration files

            The placeholders ``%system``, ``%prefix``, ``%user`` and
            ``%pwd`` can be used to refer to the sources 1-4 above.

    Returns:
        dict of str -> str:
            A dictionary object that contains the merged configuration options
            from the sources mentioned above.

    See Also:
        :obj:`_config_file_to_dict`, :obj:`_config_environment_to_dict`:
    """

    # Prepare defaults.
    if defaults is None:
        defaults = {}
    if 'transport.socket.enabled' not in defaults:
        defaults['transport.socket.enabled'] = '1'
    if 'introspection.enabled' not in defaults:
        defaults['introspection.enabled'] = '1'
    if platform.system() == 'Windows':
        system_config_file = "c:\\rsb.conf"
    else:
        system_config_file = "/etc/rsb.conf"

    # Configure sources.
    debug = CONFIG_DEBUG_VARIABLE in os.environ

    file_index = [1]

    def from_file(config_file, description):
        def process_file(partial):
            if debug:
                if file_index[0] == 1:
                    print('  1. Configuration files')
                print(('     %d. %s "%s" %s'
                       % (file_index[0], description, config_file,
                          'exists' if os.path.exists(config_file)
                          else 'does not exist')))
                file_index[0] += 1
            return _config_file_to_dict(config_file, partial)
        return process_file

    def process_environment(partial):
        if debug:
            print('  2. Environment variables with prefix RSB_')
        return _config_environment_to_dict(partial, debug=debug)

    def process_spec(spec):
        if spec == CONFIG_FILE_KEY_SYSTEM:
            return from_file(system_config_file,
                             'System wide config file')
        elif spec == CONFIG_FILE_KEY_PREFIX:
            return from_file('%s/etc/rsb.conf' % rsb.util.prefix(),
                             'Prefix wide config file')
        elif spec == CONFIG_FILE_KEY_USER:
            return from_file(os.path.expanduser('~/.config/rsb.conf'),
                             'User config file')
        elif spec == CONFIG_FILE_KEY_PWD:
            return from_file('rsb.conf', 'Current directory file')
        else:
            return from_file(spec, 'User specified config file')
    sources = [process_spec(f) for f in files] + [process_environment]

    # Merge sources and defaults.
    if debug:
        print('Configuring with sources (lowest priority first)')
    return reduce(lambda partial, source: source(partial), sources, defaults)


_CONFIG_TRUE_VALUES = ['1', 'true', 'yes']


def _config_value_is_true(value):
    return value in _CONFIG_TRUE_VALUES


class ParticipantConfig(object):
    """
    Describes desired configurations for newly created participants.

    Configured aspects comprise:

    * Quality of service settings
    * Error handling strategies (not currently used)
    * Employed transport mechanisms

      * Their configurations (e.g. port numbers)
      * Associated converters

    * Whether introspection should be enabled for the participant
      (enabled by default)

    .. codeauthor:: jmoringe
    """

    class Transport(object):
        """
        Describes configurations of transports connectors.

        The configured aspects consist of

        * Transport name
        * Enabled vs. Disabled
        * Optional converter selection
        * Transport-specific options

        .. codeauthor:: jmoringe
        """

        def __init__(self, name, options=None, converters=None):
            self.__name = name
            self.__enabled = _config_value_is_true(options.get('enabled', '0'))

            # Extract freestyle options for the transport.
            if options is None:
                self.__options = {}
            else:
                self.__options = {key: value
                                  for (key, value) in list(options.items())
                                  if '.' not in key and
                                  key != 'enabled'}
            # Find converter selection rules
            self.__converters = converters
            self.__converter_rules = {
                key[len("converter.python."):]: value
                for (key, value) in list(options.items())
                if key.startswith('converter.python')}

        def get_name(self):
            return self.__name

        name = property(get_name)

        def is_enabled(self):
            return self.__enabled

        def set_enabled(self, flag):
            self.__enabled = flag

        enabled = property(is_enabled, set_enabled)

        def get_converters(self):
            return self.__converters

        def set_converters(self, converters):
            self.__converters = converters

        converters = property(get_converters, set_converters)

        def get_converter_rules(self):
            return self.__converter_rules

        def set_converter_rules(self, converter_rules):
            self.__converter_rules = converter_rules

        converter_rules = property(get_converter_rules, set_converter_rules)

        def get_options(self):
            return self.__options

        options = property(get_options)

        def __deepcopy__(self, memo):
            result = copy.copy(self)
            result.__converters = copy.deepcopy(self.__converters, memo)
            result.__converter_rules = copy.deepcopy(
                self.__converter_rules, memo)
            result.__options = copy.deepcopy(self.__options, memo)
            return result

        def __str__(self):
            return ('ParticipantConfig.Transport[%s, enabled = %s, '
                    'converters = %s, converter_rules = %s, options = %s]'
                    % (self.__name, self.__enabled, self.__converters,
                       self.__converter_rules, self.__options))

        def __repr__(self):
            return str(self)

    def __init__(self,
                 transports=None,
                 options=None,
                 qos=None,
                 introspection=False):
        if transports is None:
            self.__transports = {}
        else:
            self.__transports = transports

        if options is None:
            self.__options = {}
        else:
            self.__options = options

        if qos is None:
            self.__qos = QualityOfServiceSpec()
        else:
            self.__qos = qos

        self.__introspection = introspection

    def get_transports(self, include_disabled=False):
        return [t for t in list(self.__transports.values())
                if include_disabled or t.is_enabled()]

    transports = property(get_transports)

    def get_transport(self, name):
        return self.__transports[name]

    def get_quality_of_service_spec(self):
        return self.__qos

    def set_quality_of_service_spec(self, new_value):
        self.__qos = new_value

    quality_of_service_spec = property(get_quality_of_service_spec,
                                       set_quality_of_service_spec)

    def get_introspection(self):
        return self.__introspection

    def set_introspection(self, new_value):
        self.__introspection = new_value

    introspection = property(get_introspection, set_introspection)

    def __deepcopy__(self, memo):
        result = copy.copy(self)
        result.__transports = copy.deepcopy(self.__transports, memo)
        result.__options = copy.deepcopy(self.__options, memo)
        return result

    def __str__(self):
        return 'ParticipantConfig[%s, options = %s, ' \
               'qos = %s, introspection = %s]' \
               % (list(self.__transports.values()), self.__options, self.__qos,
                  self.__introspection)

    def __repr__(self):
        return str(self)

    @classmethod
    def __from_dict(cls, options):
        def section_options(section):
            return [(key[len(section) + 1:], value)
                    for (key, value) in list(options.items())
                    if key.startswith(section)]
        result = ParticipantConfig()

        # Quality of service
        qos_options = dict(section_options('qualityofservice'))
        result.__qos.set_reliability(
            QualityOfServiceSpec.Reliability.from_string(
                qos_options.get(
                    'reliability',
                    QualityOfServiceSpec().get_reliability().__str__())))
        result.__qos.set_ordering(
            QualityOfServiceSpec.Ordering.from_string(
                qos_options.get(
                    'ordering',
                    QualityOfServiceSpec().get_ordering().__str__())))

        # Transport options
        for transport in ['spread', 'socket', 'inprocess']:
            transport_options = dict(
                section_options('transport.%s' % transport))
            if transport_options:
                result.__transports[transport] = cls.Transport(
                    transport, transport_options)

        # Introspection options
        introspection_options = dict(section_options('introspection'))
        result.__introspection = _config_value_is_true(
            introspection_options.get('enabled', '1'))

        return result

    @classmethod
    def from_dict(cls, options):
        return cls.__from_dict(options)

    @classmethod
    def from_file(cls, path, defaults=None):
        """
        Parse the configuration options specified in the provided config file.

        Obtain configuration options from the configuration file
        ``path``, store them in a :obj:`ParticipantConfig` object and
        return it.

        A simple configuration file may look like this::

            [transport.spread]
            host = azurit # default type is string
            port = 5301 # types can be specified in angle brackets
            # A comment

        Args:
            path:
                File of path
            defaults (dict of str -> str):
                dictionary with default options

        Returns:
            ParticipantConfig:
                A new :obj:`ParticipantConfig` object containing the options
                read from ``path``.


        See Also:
            :obj:`fromEnvironment`, :obj:`fromDefaultSources`
        """
        return cls.__from_dict(_config_file_to_dict(path, defaults))

    @classmethod
    def from_environment(cls, defaults=None):
        """
        Parse the configuration options specified via environment variables.

        Obtain configuration options from environment variables, store
        them in a :obj:`ParticipantConfig` object and return
        it. Environment variable names are mapped to RSB option names
        as illustrated in the following example::

           RSB_TRANSPORT_SPREAD_PORT -> transport spread port

        Args:
            defaults (dict of str -> str):
                dictionary with default options

        Returns:
            ParticipantConfig:
                :obj:`ParticipantConfig` object that contains the merged
                configuration options from ``defaults`` and relevant
                environment variables.

        See Also:
            :obj:`fromFile`, :obj:`fromDefaultSources`
        """
        return cls.__from_dict(_config_environment_to_dict(defaults))

    @classmethod
    def from_default_sources(cls, defaults=None):
        r"""
        Parse the configuration from a default set of sources.

        Obtain configuration options from multiple sources, store them
        in a :obj:`ParticipantConfig` object and return it. The following
        sources of configuration information will be consulted:

         1. ``/etc/rsb.conf``
         2. ``$prefix/etc/rsb.conf``
         3. ``~/.config/rsb.conf``
         4. ``$(PWD)/rsb.conf``
         5. Environment Variables

        Args:
            defaults (dict of str -> str):
                dictionary with default options

        Returns:
            ParticipantConfig:
                A :obj:`ParticipantConfig` object that contains the merged
                configuration options from the sources mentioned above.

        See Also:
            :obj:`fromFile`, :obj:`fromEnvironment`
        """

        return cls.__from_dict(_config_default_sources_to_dict(defaults))


def converters_from_transport_config(transport):
    """
    Return a converter selection strategy suitable for the given transport.

    Returns an object implementing the
    :obj:`rsb.converter.ConverterSelectionStrategy` protocol suitable for
    ``transport``.

    If ``transport.converters`` is not ``None``, it is used
    unmodified. Otherwise the specification in
    ``transport.converter_rules`` is used.

    Returns:
        ConverterSelectionStrategy:
            The constructed ConverterSelectionStrategy object.

    """

    # There are two possible ways to configure converters:
    # 1) transport.converters: this is either None or an object
    #    implementing the "ConverterSelectionStrategy protocol"
    # 2) when transport.converters is None, transport.converter_rules
    #    is used to construct an object implementing the
    #    "ConverterSelectionStrategy protocol"
    if transport.converters is not None:
        return transport.converters

    # Obtain a consistent converter set for the wire-type of
    # the transport:
    # 1. Find global converter map for the wire-type
    # 2. Find configuration options that specify converters
    #    for the transport
    # 3. Add converters from the global map to the unambiguous map of
    #    the transport, resolving conflicts based on configuration
    #    options when necessary
    # TODO hack!
    wire_type = bytes

    import rsb
    import rsb.converter
    converter_map = rsb.converter.UnambiguousConverterMap(wire_type)
    # Try to add converters form global map
    global_map = rsb.converter.get_global_converter_map(wire_type)
    for ((wire_schema, data_type), converter) \
            in list(global_map.get_converters().items()):
        # Converter can be added if converterOptions does not
        # contain a disambiguation that gives precedence to a
        # different converter. map may still raise an
        # exception in case of ambiguity.
        if wire_schema not in transport.converter_rules \
           or data_type.__name__ == transport.converter_rules[wire_schema]:
            converter_map.add_converter(converter)
    return converter_map


class Scope(object):
    """
    A scope defines a channel of the hierarchical unified bus covered by RSB.

    It is defined by a surface syntax like ``"/a/deep/scope"``.

    .. codeauthor:: jwienke
    """

    __COMPONENT_SEPARATOR = "/"
    __COMPONENT_REGEX = re.compile("^[-_a-zA-Z0-9]+$")

    @classmethod
    def ensure_scope(cls, thing):
        if isinstance(thing, cls):
            return thing
        else:
            return Scope(thing)

    def __init__(self, string_rep):
        """
        Parse a scope from a string representation.

        Args:
            string_rep (str or unicode):
                string representation of the scope
        Raises:
            ValueError:
                if ``string_rep`` does not have the right syntax
        """

        if len(string_rep) == 0:
            raise ValueError("The empty string does not designate a "
                             "scope; Use '/' to designate the root scope.")

        if isinstance(string_rep, str):
            try:
                string_rep = string_rep.encode('ASCII').decode('ASCII')
            except UnicodeEncodeError as e:
                raise ValueError('Scope strings have be encodable as '
                                 'ASCII-strings, but the supplied scope '
                                 'string cannot be encoded as ASCII-string: %s'
                                 % e)

        # append missing trailing slash
        if string_rep[-1] != self.__COMPONENT_SEPARATOR:
            string_rep += self.__COMPONENT_SEPARATOR

        raw_components = string_rep.split(self.__COMPONENT_SEPARATOR)
        if len(raw_components) < 1:
            raise ValueError("Empty scope is not allowed.")
        if len(raw_components[0]) != 0:
            raise ValueError("Scope must start with a slash. "
                             "Given was '%s'." % string_rep)
        if len(raw_components[-1]) != 0:
            raise ValueError("Scope must end with a slash. "
                             "Given was '%s'." % string_rep)

        self.__components = raw_components[1:-1]

        for com in self.__components:
            if not self.__COMPONENT_REGEX.match(com):
                raise ValueError("Invalid character in component %s. "
                                 "Given was scope '%s'." % (com, string_rep))

    def get_components(self):
        """
        Return all components of the scope as an ordered list.

        Components are the names between the separator character '/'. The first
        entry in the list is the highest level of hierarchy. The scope '/'
        returns an empty list.

        Returns:
            list:
                components of the represented scope as ordered list with
                highest level as first entry
        """
        return copy.copy(self.__components)

    components = property(get_components)

    def to_string(self):
        """
        Return a formal string representation with leading an trailing slashes.

        Returns:
            str:
                string representation of the scope
        """

        string = self.__COMPONENT_SEPARATOR
        for com in self.__components:
            string += com
            string += self.__COMPONENT_SEPARATOR
        return string

    def to_bytes(self):
        """
        Encode the string representation as ASCII-encoded bytes.

        Returns:
            bytes:
                encoded string representation
        """
        return self.to_string().encode('ASCII')

    def concat(self, child_scope):
        """
        Create a subscope of this one by appending the given other scope.

        Create a new scope that is a sub-scope of this one with the
        subordinated scope described by the given argument. E.g.
        ``"/this/is/".concat("/a/test/")`` results in ``"/this/is/a/test"``.

        Args:
            child_scope (Scope):
                child to concatenate to the current scope for forming a
                sub-scope

        Returns:
            Scope:
                new scope instance representing the created sub-scope
        """
        new_scope = Scope("/")
        new_scope.__components = copy.copy(self.__components)
        new_scope.__components += child_scope.__components
        return new_scope

    def is_sub_scope_of(self, other):
        """
        Test whether this scope is a sub-scope of the given other scope.

        The result of this method is ``True`` if the other scope is a prefix
        of this scope. E.g. "/a/b/" is a sub-scope of "/a/".

        Args:
            other (Scope):
                other scope to test

        Returns:
            Bool:
                ``True`` if this is a sub-scope of the other scope, equality
                gives ``False``, too
        """

        if len(self.__components) <= len(other.__components):
            return False

        return other.__components == \
            self.__components[:len(other.__components)]

    def is_super_scope_of(self, other):
        """
        Check whether this instances is a super scope of the given one.

        Inverse operation of :obj:`is_sub_scope_of`.

        Args:
            other (Scope):
                other scope to test

        Returns:
            Bool:
                ``True`` if this scope is a strict super scope of the other
                scope. Equality also gives ``False``.

        """

        if len(self.__components) >= len(other.__components):
            return False

        return self.__components == other.__components[:len(self.__components)]

    def super_scopes(self, include_self=False):
        """
        Generate all super scopes of this scope including the root scope "/".

        The returned list of scopes is ordered by hierarchy with "/" being the
        first entry.

        Args:
            include_self (Bool):
                if set to ``True``, this scope is also included as last element
                of the returned list

        Returns:
            list of Scopes:
                list of all super scopes ordered by hierarchy, "/" being first
        """

        supers = []

        max_index = len(self.__components)
        if not include_self:
            max_index -= 1
        for i in range(max_index + 1):
            super_scope = Scope("/")
            super_scope.__components = self.__components[:i]
            supers.append(super_scope)

        return supers

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.__components == other.__components

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.to_string())

    def __lt__(self, other):
        return self.to_string() < other.to_string()

    def __le__(self, other):
        return self.to_string() <= other.to_string()

    def __gt__(self, other):
        return self.to_string() > other.to_string()

    def __ge__(self, other):
        return self.to_string() >= other.to_string()

    def __str__(self):
        return "Scope[%s]" % self.to_string()

    def __repr__(self):
        return '%s("%s")' % (self.__class__.__name__, self.to_string())


class MetaData(object):
    """
    Stores RSB-specific and user-supplied meta-data items for an event.

    .. codeauthor:: jmoringe
    """

    def __init__(self,
                 create_time=None, send_time=None,
                 receive_time=None, deliver_time=None,
                 user_times=None, user_infos=None):
        """
        Construct a new :obj:`MetaData` object.

        Args:
            create_time:
                A timestamp designating the time at which the associated event
                was created.
            send_time:
                A timestamp designating the time at which the associated event
                was sent onto the bus.
            receive_time:
                A timestamp designating the time at which the associated event
                was received from the bus.
            deliver_time:
                A timestamp designating the time at which the associated event
                was delivered to the user-level handler by RSB.
            user_times (dict of str -> float):
                A dictionary of user-supplied timestamps. dict from string name
                to double value as seconds since unix epoche
            user_infos (dict of str -> str):
                A dictionary of user-supplied meta-data items.
        """
        if create_time is None:
            self.__create_time = time.time()
        else:
            self.__create_time = create_time
        self.__send_time = send_time
        self.__receive_time = receive_time
        self.__deliver_time = deliver_time
        if user_times is None:
            self.__user_times = {}
        else:
            self.__user_times = user_times
        if user_infos is None:
            self.__user_infos = {}
        else:
            self.__user_infos = user_infos

    def get_create_time(self):
        return self.__create_time

    def set_create_time(self, create_time=None):
        if create_time is None:
            self.__create_time = time.time()
        else:
            self.__create_time = create_time

    create_time = property(get_create_time, set_create_time)

    def get_send_time(self):
        return self.__send_time

    def set_send_time(self, send_time=None):
        if send_time is None:
            self.__send_time = time.time()
        else:
            self.__send_time = send_time

    send_time = property(get_send_time, set_send_time)

    def get_receive_time(self):
        return self.__receive_time

    def set_receive_time(self, receive_time=None):
        if receive_time is None:
            self.__receive_time = time.time()
        else:
            self.__receive_time = receive_time

    receive_time = property(get_receive_time, set_receive_time)

    def get_deliver_time(self):
        return self.__deliver_time

    def set_deliver_time(self, deliver_time=None):
        if deliver_time is None:
            self.__deliver_time = time.time()
        else:
            self.__deliver_time = deliver_time

    deliver_time = property(get_deliver_time, set_deliver_time)

    def get_user_times(self):
        return self.__user_times

    def set_user_times(self, user_times):
        self.__user_times = user_times

    def set_user_time(self, key, timestamp=None):
        if timestamp is None:
            self.__user_times[key] = time.time()
        else:
            self.__user_times[key] = timestamp

    user_times = property(get_user_times, set_user_times)

    def get_user_infos(self):
        return self.__user_infos

    def set_user_infos(self, user_infos):
        self.__user_infos = user_infos

    def set_user_info(self, key, value):
        self.__user_infos[key] = value

    user_infos = property(get_user_infos, set_user_infos)

    def __eq__(self, other):
        return (self.__create_time == other.__create_time) and \
            (self.__send_time == other.__send_time) and \
            (self.__receive_time == other.__receive_time) and \
            (self.__deliver_time == other.__deliver_time) and \
            (self.__user_infos == other.__user_infos) and \
            (self.__user_times == other.__user_times)

    def __neq__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return ('%s[createTime= %s, sendTime = %s, receiveTime = %s, '
                'deliverTime = %s, userTimes = %s, userInfos = %s]'
                % ('MetaData',
                   self.__create_time, self.__send_time, self.__receive_time,
                   self.__deliver_time, self.__user_times, self.__user_infos))

    def __repr__(self):
        return self.__str__()


class EventId(object):
    """
    Uniquely identifies an Event.

    This is done by the sending participants ID and a sequence number within
    this participant. Optional conversion to uuid is possible.

    .. codeauthor:: jwienke
    """

    def __init__(self, participant_id, sequence_number):
        self.__participant_id = participant_id
        self.__sequence_number = sequence_number
        self.__id = None

    def get_participant_id(self):
        """
        Return the sender id of this id.

        Returns:
            uuid.UUID:
                sender id
        """
        return self.__participant_id

    def set_participant_id(self, participant_id):
        """
        Set the participant id of this event.

        Args:
            participant_id (uuid.UUID):
                sender id to set.
        """
        self.__participant_id = participant_id

    participant_id = property(get_participant_id, set_participant_id)

    def get_sequence_number(self):
        """
        Return the sequence number of this id.

        Returns:
            int: sequence number of the id.
        """
        return self.__sequence_number

    def set_sequence_number(self, sequence_number):
        """
        Set the sequence number of this id.

        Args:
            sequence_number (int):
                new sequence number of the id.
        """
        self.__sequence_number = sequence_number

    sequence_number = property(get_sequence_number, set_sequence_number)

    def get_as_uuid(self):
        """
        Return a UUID encoded version of this id.

        Returns:
            uuid.uuid:
                id of the event as UUID
        """

        if self.__id is None:
            self.__id = uuid.uuid5(self.__participant_id,
                                   '%08x' % self.__sequence_number)
        return self.__id

    def __eq__(self, other):
        return (self.__sequence_number == other.__sequence_number) and \
            (self.__participant_id == other.__participant_id)

    def __neq__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return "EventId(%r, %r)" % (self.__participant_id,
                                    self.__sequence_number)

    def __hash__(self):
        prime = 31
        result = 1
        result = prime * result + hash(self.__participant_id)
        result = prime * result + \
            (self.__sequence_number ^ (self.__sequence_number >> 32))
        return result


class Event(object):
    """
    Basic event class.

    Events are often caused by other events, which e.g. means that their
    contained payload was calculated on the payload of one or more other
    events.

    To express these relations each event contains a set of EventIds that
    express the direct causes of the event. This means, transitive event causes
    are not modeled.

    Cause handling is inspired by the ideas proposed in: David Luckham, The
    Power of Events, Addison-Wessley, 2007

    .. codeauthor:: jwienke
    """

    def __init__(self,
                 event_id=None,
                 scope=Scope("/"),
                 method=None,
                 data=None,
                 data_type=object,
                 meta_data=None,
                 user_infos=None,
                 user_times=None,
                 causes=None):
        """
        Construct a new event with undefined type, root scope and no data.

        Args:
            event_id (EventId):
                The id of this event
            scope (Scope or accepted by Scope constructor):
                A :obj:`Scope` designating the channel on which the event will
                be published.
            method (str):
                A string designating the "method category" which identifies the
                role of the event in some communication patters. Examples are
                ``"REQUEST"`` and ``"REPLY"``.
            data:
                data contained in this event
            data_type (types.TypeType):
                python data type of the contained data
            meta_data (MetaData):
                meta data to use for the new event
            user_infos (dict of str -> str):
                key-value like store of user infos to add to the meta data of
                this event
            user_times (dict of str -> str):
                additional timestamps to add to the meta data. dict from string
                timestamp name to value of timestamp as dobule of seconds unix
                epoch
            causes (list):
                A list of :obj:`EventId` instances of events which causes the
                newly constructed events.
        """

        self.__id = event_id
        self.__scope = Scope.ensure_scope(scope)
        self.__method = method
        self.__data = data
        if data_type is None:
            raise ValueError("Type must not be None")
        self.__type = data_type
        if meta_data is None:
            self.__meta_data = MetaData()
        else:
            self.__meta_data = meta_data
        if user_infos is not None:
            for (key, value) in list(user_infos.items()):
                self.__meta_data.get_user_infos()[key] = value
        if user_times is not None:
            for (key, value) in list(user_times.items()):
                self.__meta_data.get_user_times()[key] = value
        if causes is not None:
            self.__causes = copy.copy(causes)
        else:
            self.__causes = []

    def get_sequence_number(self):
        """
        Return the sequence number of this event.

        .. deprecated:: 0.13
           use :meth:`getId` instead

        Returns:
            int:
                sequence number of the event.
        """
        return self.get_event_id().get_sequence_number()

    sequence_number = property(get_sequence_number)

    def get_event_id(self):
        """
        Return the id of this event.

        Returns:
            int:
                id of the event

        Raises:
            RuntimeError:
                if the event does not have an id so far
        """

        if self.__id is None:
            raise RuntimeError("The event does not have an ID so far.")
        return self.__id

    def set_event_id(self, event_id):
        self.__id = event_id

    event_id = property(get_event_id, set_event_id)

    def get_scope(self):
        """
        Return the scope of this event.

        Returns:
            Scope:
                scope
        """

        return self.__scope

    def set_scope(self, scope):
        """
        Set the scope of this event.

        Args:
            scope (Scope):
                scope to set
        """

        self.__scope = scope

    scope = property(get_scope, set_scope)

    def get_sender_id(self):
        """
        Return the sender id of this event.

        .. deprecated:: 0.13

           use :func:`getId` instead

        Returns:
            uuid.UUID:
                sender id
        """
        return self.get_event_id().get_participant_id()

    sender_id = property(get_sender_id)

    def get_method(self):
        """
        Return the method of this event.

        Returns:
            str:
                A string designating the method of this event of ``None`` if
                this event does not have a method.
        """
        return self.__method

    def set_method(self, method):
        """
        Set the method of this event.

        Args:
            method (str):
                The new method. ``None`` is allowed.
        """
        self.__method = method

    method = property(get_method, set_method)

    def get_data(self):
        """
        Return the user data of this event.

        Returns:
            user data
        """

        return self.__data

    def set_data(self, data):
        """
        Set the user data of this event.

        Args:
            data:
                user data
        """

        self.__data = data

    data = property(get_data, set_data)

    def get_data_type(self):
        """
        Return the type of the user data of this event.

        Returns:
            user data type

        """

        return self.__type

    def set_data_type(self, data_type):
        """
        Set the type of the user data of this event.

        Args:
            the_type:
                user data type
        """

        self.__type = data_type

    data_type = property(get_data_type, set_data_type)

    def get_meta_data(self):
        return self.__meta_data

    def set_meta_data(self, meta_data):
        self.__meta_data = meta_data

    meta_data = property(get_meta_data, set_meta_data)

    def add_cause(self, the_id):
        """
        Add a causing EventId to the causes of this event.

        Args:
            the_id (EventId):
                id to add

        Returns:
            bool:
                True if the id was newly added, else False
        """
        if the_id in self.__causes:
            return False
        else:
            self.__causes.append(the_id)
            return True

    def remove_cause(self, the_id):
        """
        Remove a causing EventId from the causes of this event.

        Args:
            the_id (EventId):
                id to remove

        Returns:
            bool:
                True if the id was remove, else False (because it did not
                exist)
        """
        if the_id in self.__causes:
            self.__causes.remove(the_id)
            return True
        else:
            return False

    def is_cause(self, the_id):
        """
        Check whether an id of an event is marked as a cause for this event.

        Args:
            the_id (EventId):
                id to check

        Returns:
            bool:
                True if the id is a cause of this event, else False
        """
        return the_id in self.__causes

    def get_causes(self):
        """
        Return all causes of this event.

        Returns:
            list of EventIds:
                causing event ids
        """
        return self.__causes

    def set_causes(self, causes):
        """
        Overwrite the cause vector of this event with the given one.

        Args:
            causes (list of EventId):
                new cause vector
        """
        self.__causes = causes

    causes = property(get_causes, set_causes)

    def __str__(self):
        print_data = str(self.__data)
        if len(print_data) > 100:
            print_data = print_data[:100] + '...'
        print_data = ''.join(['\\x%x' % ord(c)
                              if ord(c) < 32 else c for c in print_data])
        return "%s[id = %s, scope = '%s', data = '%s', type = '%s', " \
            "method = '%s', meta_data = %s, causes = %s]" \
            % ("Event", self.__id, self.__scope, print_data, self.__type,
               self.__method, self.__meta_data, self.__causes)

    def __repr__(self):
        return self.__str__()

    def __eq__(self, other):
        try:
            return (self.__id == other.__id) and \
                (self.__scope == other.__scope) and \
                (self.__type == other.__type) and \
                (self.__data == other.__data) and \
                (self.__meta_data == other.__meta_data) and \
                (self.__causes == other.__causes)
        except (TypeError, AttributeError):
            return False

    def __neq__(self, other):
        return not self.__eq__(other)


class Hook(object):
    """
    A mutable collection of callback functions that can be called together.

    .. codeauthor:: jmoringe
    """

    def __init__(self):
        self.__lock = threading.RLock()
        self.__handlers = []

    def run(self, *args, **kwargs):
        with self.__lock:
            for handler in self.__handlers:
                handler(*args, **kwargs)

    def add_handler(self, handler):
        with self.__lock:
            self.__handlers.append(handler)

    def remove_handler(self, handler):
        with self.__lock:
            self.__handlers.remove(handler)


participant_creation_hook = Hook()

participant_destruction_hook = Hook()


class Participant(object):
    """
    Base class for specialized bus participant classes.

    Has a unique id and a scope.

    .. codeauthor:: jmoringe
    """

    def __init__(self, scope, config):
        """
        Construct a new Participant.

        This should not be done by clients.

        Args:
            scope (Scope or accepted by Scope constructor):
                scope of the bus channel.
            config (ParticipantConfig):
                Configuration that the participant should use

        See Also:
            :obj:`create_listener`, :obj:`create_informer`, :obj:`create_server`,
            :obj:`create_remote_server`
        """
        self.__id = uuid.uuid4()
        self.__scope = Scope.ensure_scope(scope)
        self.__config = config

    def get_participant_id(self):
        return self.__id

    def set_participant_id(self, participant_id):
        self.__id = participant_id

    participant_id = property(get_participant_id, set_participant_id)

    def get_scope(self):
        return self.__scope

    def set_scope(self, scope):
        self.__scope = scope

    scope = property(get_scope, set_scope)

    def get_config(self):
        return self.__config

    config = property(get_config)

    def get_transport_ur_ls(self):
        """
        Return of list transport URLs for all used transports.

        Returns:
            set:
                Set of transport URLs.
        """
        return set()

    transport_ur_ls = property(get_transport_ur_ls)

    def activate(self):
        pass

    def deactivate(self):
        """
        Deactivate a participant by tearing down all connection logic.

        This needs to be called in case you want to ensure that programs can
        terminate correctly.
        """
        participant_destruction_hook.run(self)

    def __enter__(self):
        return self

    def __exit__(self, exec_type, exec_value, traceback):
        self.deactivate()

    @classmethod
    def get_connectors(cls, direction, config):
        if direction not in ('in', 'in-pull', 'out'):
            raise ValueError('Invalid direction: %s (valid directions '
                             'are "in", "in-pull" and "out")' % direction)
        if len(config.get_transports()) == 0:
            raise ValueError('No transports specified (config is %s)' % config)

        transports = []
        for transport in config.get_transports():
            factory = rsb.transport.get_transport_factory(transport.get_name())
            converters = converters_from_transport_config(transport)
            if direction == 'in':
                transports.append(
                    factory.create_in_push_connector(converters,
                                                     transport.get_options()))
            elif direction == 'in-pull':
                transports.append(
                    factory.create_in_pull_connector(converters,
                                                     transport.get_options()))
            elif direction == 'out':
                transports.append(
                    factory.create_out_connector(converters,
                                                 transport.get_options()))
            else:
                assert False
        return transports


class Informer(Participant):
    """
    Event-sending part of the communication pattern.

    .. codeauthor:: jwienke
    .. codeauthor:: jmoringe
    """

    def __init__(self, scope, config, data_type,
                 configurator=None):
        """
        Construct a new :obj:`Informer`.

        The new instance publishes :obj:`Events <Event>` carrying payloads of
        type ``type`` on ``scope``.

        Args:
            scope (Scope or accepted by Scope constructor):
                scope of the informer
            config (ParticipantConfig):
                The configuration that should be used by this :obj:`Informer`.
            data_type (types.TypeType):
                A Python object designating the type of objects that will be
                sent via the new :obj:`Informer`. Instances of subtypes are
                permitted as well.
            configurator:
                Out route configurator to manage sending of events through out
                connectors.

        .. todo::

           maybe provide an automatic type identifier deduction for default
           types?

        See Also:
            :obj:`create_informer`
        """
        super(Informer, self).__init__(scope, config)

        self.__logger = get_logger_by_class(self.__class__)

        # TODO check that type can be converted
        if data_type is None:
            raise ValueError("data_type must not be None")
        self.__type = data_type
        self.__sequence_number = 0
        self.__configurator = None

        self.__active = False
        self.__mutex = threading.Lock()

        if configurator:
            self.__configurator = configurator
        else:
            connectors = self.get_connectors('out', config)
            for connector in connectors:
                connector.set_quality_of_service_spec(
                    config.get_quality_of_service_spec())
            self.__configurator = rsb.eventprocessing.OutRouteConfigurator(
                connectors=connectors)
        self.__configurator.set_quality_of_service_spec(
            config.get_quality_of_service_spec())
        self.__configurator.scope = self.scope

        self.__activate()

    def __del__(self):
        self.__logger.debug("Destructing Informer")
        if self.__active:
            self.deactivate()

    def get_transport_urls(self):
        return self.__configurator.get_transport_urls()

    transport_urls = property(get_transport_urls)

    def get_data_type(self):
        """
        Return the type of data sent by this informer.

        Returns:
            type of sent data
        """
        return self.__type

    data_type = property(get_data_type)

    def publish_data(self, data, user_infos=None, user_times=None):
        # TODO check activation
        self.__logger.debug("Publishing data '%s'", data)
        event = Event(scope=self.scope,
                      data=data, data_type=type(data),
                      user_infos=user_infos, user_times=user_times)
        return self.publish_event(event)

    def publish_event(self, event):
        """
        Publish a predefined event.

        The caller must ensure that the event has the appropriate scope and
        type according to the :obj:`Informer`'s settings.

        Args:
            event (Event):
                the event to send
        """
        # TODO check activation

        if not event.scope == self.scope \
                and not event.scope.is_sub_scope_of(self.scope):
            raise ValueError("Scope %s of event %s is not a sub-scope of "
                             "this informer's scope %s."
                             % (event.scope, event, self.scope))
        if not isinstance(event.data, self.data_type):
            raise ValueError("The payload %s of event %s does not match "
                             "this informer's type %s."
                             % (event.data, event, self.data_type))

        with self.__mutex:
            event.event_id = EventId(self.participant_id,
                                     self.__sequence_number)
            self.__sequence_number += 1
        self.__logger.debug("Publishing event '%s'", event)
        self.__configurator.handle(event)
        return event

    def __activate(self):
        with self.__mutex:
            if self.__active:
                raise RuntimeError("Activate called even though informer "
                                   "was already active")

            self.__logger.info("Activating informer")

            self.__configurator.activate()

            self.__active = True

        self.activate()

    def deactivate(self):
        with self.__mutex:
            if not self.__active:
                self.__logger.info("Deactivate called even though informer "
                                   "was not active")

            self.__logger.info("Deactivating informer")

            self.__active = False

            self.__configurator.deactivate()

        super(Informer, self).deactivate()


class Listener(Participant):
    """
    Event-receiving part of the communication pattern.

    .. codeauthor:: jwienke
    .. codeauthor:: jmoringe
    """

    def __init__(self, scope, config,
                 configurator=None,
                 receiving_strategy=None):
        """
        Create a new :obj:`Listener` for ``scope``.

        Args:
            scope (Scope or accepted by Scope constructor):
                The scope of the channel in which the new listener should
                participate.
            config (ParticipantConfig):
                The configuration that should be used by this :obj:`Listener`.
            configurator:
                An in route configurator to manage the receiving of events from
                in connectors and their filtering and dispatching.

        See Also:
            :obj:`create_listener`
        """
        super(Listener, self).__init__(scope, config)

        self.__logger = get_logger_by_class(self.__class__)

        self.__filters = []
        self.__handlers = []
        self.__configurator = None
        self.__active = False
        self.__mutex = threading.Lock()

        if configurator:
            self.__configurator = configurator
        else:
            connectors = self.get_connectors('in', config)
            for connector in connectors:
                connector.set_quality_of_service_spec(
                    config.get_quality_of_service_spec())
            self.__configurator = rsb.eventprocessing.InPushRouteConfigurator(
                connectors=connectors,
                receiving_strategy=receiving_strategy)
        self.__configurator.set_scope(self.scope)

        self.__activate()

    def __del__(self):
        if self.__active:
            self.deactivate()

    def get_transport_urls(self):
        return self.__configurator.get_transport_urls()

    transport_urls = property(get_transport_urls)

    def __activate(self):
        # TODO commonality with Informer... refactor
        with self.__mutex:
            if self.__active:
                raise RuntimeError("Activate called even though listener "
                                   "was already active")

            self.__logger.info("Activating listener")

            self.__configurator.activate()

            self.__active = True

        self.activate()

    def deactivate(self):
        with self.__mutex:
            if not self.__active:
                raise RuntimeError("Deactivate called even though listener "
                                   "was not active")

            self.__logger.info("Deactivating listener")

            self.__configurator.deactivate()

            self.__active = False

        super(Listener, self).deactivate()

    def add_filter(self, the_filter):
        """
        Append a filter to restrict the events received by this listener.

        Args:
            the_filter:
                filter to add
        """

        with self.__mutex:
            self.__filters.append(the_filter)
            self.__configurator.filter_added(the_filter)

    def get_filters(self):
        """
        Return all registered filters of this listener.

        Returns:
            list of filters
        """

        with self.__mutex:
            return list(self.__filters)

    def add_handler(self, handler, wait=True):
        """
        Add ``handler`` to the list of handlers being invoked on new events.

        Args:
            handler:
                Handler to add. callable with one argument, the event.
            wait:
                If set to ``True``, this method will return only after the
                handler has completely been installed and will receive the next
                available message. Otherwise it may return earlier.
        """

        with self.__mutex:
            if handler not in self.__handlers:
                self.__handlers.append(handler)
                self.__configurator.handler_added(handler, wait)

    def remove_handler(self, handler, wait=True):
        """
        Remove ``handler`` from the list of handlers this listener invokes.

        Args:
            handler:
                Handler to remove.
            wait:
                If set to ``True``, this method will return only after the
                handler has been completely removed from the event processing
                and will not be called anymore from this listener.
        """

        with self.__mutex:
            if handler in self.__handlers:
                self.__configurator.handlerRemoved(handler, wait)
                self.__handlers.remove(handler)

    def get_handlers(self):
        """
        Return the list of all registered handlers.

        Returns:
            list of callables accepting an Event:
                list of handlers to execute on matches
        """
        with self.__mutex:
            return list(self.__handlers)


class Reader(Participant):
    """
    Receives events by manually pulling them from the wire.

    Clients need to continuously call the :meth:`read` method to receive
    events. Being too slow to receive events will usually terminate the
    connection and is fatal.

    .. codeauthor:: jwienke
    """

    def __init__(self, scope, config, configurator=None,
                 receiving_strategy=None):
        """
        Create a new :obj:`Reader` for ``scope``.

        Args:
            scope (Scope or accepted by Scope constructor):
                The scope of the channel in which the new reader should
                participate.
            config (ParticipantConfig):
                The configuration that should be used by this :obj:`Reader`.
            configurator:
                An in route configurator to manage the receiving of events from
                in connectors and their filtering and dispatching.

        See Also:
            :obj:`create_reader`
        """
        super(Reader, self).__init__(scope, config)

        self.__logger = get_logger_by_class(self.__class__)

        self.__filters = []
        self.__configurator = None
        self.__active = False
        self.__mutex = threading.Lock()

        if configurator:
            self.__configurator = configurator
        else:
            connectors = self.get_connectors('in-pull', config)
            for connector in connectors:
                connector.set_quality_of_service_spec(
                    config.get_quality_of_service_spec())
            self.__configurator = rsb.eventprocessing.InPullRouteConfigurator(
                connectors=connectors, receiving_strategy=receiving_strategy)
        self.__configurator.set_scope(self.scope)

        self.__activate()

    def __del__(self):
        if self.__active:
            self.deactivate()

    def get_transport_urls(self):
        return self.__configurator.get_transport_urls()

    transport_urls = property(get_transport_urls)

    def __activate(self):
        with self.__mutex:
            if self.__active:
                raise RuntimeError("Activate called even though listener "
                                   "was already active")

            self.__logger.info("Activating listener")

            self.__configurator.activate()

            self.__active = True

        self.activate()

    def deactivate(self):
        with self.__mutex:
            if not self.__active:
                raise RuntimeError("Deactivate called even though listener "
                                   "was not active")

            self.__logger.info("Deactivating listener")

            self.__configurator.deactivate()

            self.__active = False

        super(Reader, self).deactivate()

    def read(self, block=True):
        """
        Read the next event from the wire.

        Optionally blocks until an event is available.

        Args:
            block (bool):
                If ``True``, block until the next event is received.

        Returns:
            rsb.Event
                the received event
        """
        return self.__configurator.get_receiving_strategy().raise_event(block)


__default_configuration_options = _config_default_sources_to_dict()
__default_participant_config = ParticipantConfig.from_dict(
    __default_configuration_options)


def get_default_participant_config():
    """Return the current default configuration for new objects."""
    return __default_participant_config


def set_default_participant_config(config):
    """
    Replace the default configuration for new objects.

    Args:
        config (ParticipantConfig):
            A ParticipantConfig object which contains the new defaults.
    """
    global __default_participant_config
    _logger.debug('Setting default participant config to %s', config)
    __default_participant_config = config


_introspection_display_name = __default_configuration_options.get(
    'introspection.displayname')
_introspection_initialized = False
_introspection_mutex = threading.RLock()


def _initialize_introspection():
    global _introspection_initialized
    import rsb.introspection as introspection
    with _introspection_mutex:
        if not _introspection_initialized:
            introspection.initialize(_introspection_display_name)
            _introspection_initialized = True


def create_participant(cls, scope, config, parent=None, **kwargs):
    """
    Create and returns a new participant of type `cls`.

    Args:
        cls (type):
            The type of participant that should be created. For
            example :obj:`Listener`.
        scope (Scope or accepted by :obj:`Scope` constructor):
            the scope of the new participant. Can be a :obj:`Scope` object
            or a string.
        config (ParticipantConfig):
            The configuration that should be used by the new participant.
        parent (Participant or NoneType):
            ``None`` or the :obj:`Participant` which should be considered the
            parent of the new participant.

    Returns:
        Participant:
            A new :obj:`Participant` object of type `cls`.
    """
    if config is None:
        config = get_default_participant_config()
    _register_default_transports()

    if config.introspection:
        _initialize_introspection()

    participant = cls(scope, config=config, **kwargs)
    participant_creation_hook.run(participant, parent=parent)
    return participant


def create_listener(scope, config=None, parent=None, **kwargs):
    """
    Create and returns a new :obj:`Listener` for ``scope``.

    Args:
        scope (Scope or accepted by :obj:`Scope` constructor):
            the scope of the new :obj:`Listener`. Can be a :obj:`Scope` object
            or a string.
        config (ParticipantConfig):
            The configuration that should be used by this :obj:`Listener`.
        parent (Participant or NoneType):
            ``None`` or the :obj:`Participant` which should be considered the
            parent of the new :obj:`Listener`.

    Returns:
        Listener:
            a new :obj:`Listener` object.
    """
    return create_participant(Listener, scope, config, parent,
                              **kwargs)


def create_reader(scope, config=None, parent=None, **kwargs):
    """
    Create and returns a new :obj:`Reader` for ``scope``.

    Args:
        scope (Scope or accepted by :obj:`Scope` constructor):
            the scope of the new :obj:`Reader`. Can be a :obj:`Scope` object
            or a string.
        config (ParticipantConfig):
            The configuration that should be used by this :obj:`Reader`.
        parent (Participant or NoneType):
            ``None`` or the :obj:`Participant` which should be considered the
            parent of the new :obj:`Reader`.

    Returns:
        Reader:
            a new :obj:`Reader` object.
    """
    return create_participant(Reader, scope, config, parent,
                              **kwargs)


def create_informer(scope, config=None, parent=None, data_type=object,
                    **kwargs):
    """
    Create and returns a new :obj:`Informer` for ``scope``.

    Args:
        scope (Scope or accepted by :obj:`Scope` constructor):
            The scope of the new :obj:`Informer`. Can be a :obj:`Scope` object
            or a string.
        config (ParticipantConfig):
            The configuration that should be used by this :obj:`Informer`.
        parent (Participant or NoneType):
            ``None`` or the :obj:`Participant` which should be considered the
            parent of the new :obj:`Informer`.
        data_type (types.TypeType):
            A Python object designating the type of objects that will be sent
            via the new :obj:`Informer`. Instances of subtypes are permitted as
            well.

    Returns:
        Informer:
            a new :obj:`Informer` object.
    """
    return create_participant(Informer, scope, config, parent,
                              data_type=data_type,
                              **kwargs)


def create_local_server(scope, config=None, parent=None,
                        provider=None, expose=None, methods=None,
                        **kwargs):
    """
    Create a new :obj:`LocalServer` that exposes its methods under ``scope``.

    The keyword parameters object, expose and methods can be used to
    associate an initial set of methods with the newly created server
    object.

    Args:
        scope (Scope or accepted by :obj:`Scope` constructor):
            The scope under which the newly created server should expose its
            methods.
        config (ParticipantConfig):
            The configuration that should be used by this server.
        parent (Participant or NoneType):
            ``None`` or the :obj:`Participant` which should be considered the
            parent of the new server.
        provider:
            An object the methods of which should be exposed via the newly
            created server. Has to be supplied in combination with the expose
            keyword parameter.
        expose:
            A list of names of attributes of object that should be expose as
            methods of the newly created server. Has to be supplied in
            combination with the object keyword parameter.
        methods:
            A list or tuple of lists or tuples of the length four:

            * a method name,
            * a callable implementing the method,
            * a type designating the request type of the method and
            * a type designating the reply type of the method.

    Returns:
        rsb.patterns.LocalServer:
            A newly created :obj:`LocalServer` object.
    """
    # Check arguments
    if provider is not None and expose is not None and methods is not None:
        raise ValueError('Supply either provider and expose or methods')
    if provider is None and expose is not None \
            or provider is not None and expose is None:
        raise ValueError('provider and expose have to supplied together')

    # Create the server object and potentially add methods.
    import rsb.patterns as patterns
    server = create_participant(patterns.LocalServer,
                                scope, config, parent,
                                **kwargs)
    if provider and expose:
        methods = [(name, getattr(provider, name), request_type, reply_type)
                   for (name, request_type, reply_type) in expose]
    if methods:
        for (name, func, request_type, reply_type) in methods:
            server.add_method(name, func, request_type, reply_type)
    return server


def create_remote_server(scope, config=None, parent=None, **kwargs):
    """
    Create a new :obj:`RemoteServer` that provides methods under ``scope``.

    Args:
        scope (Scope or accepted by Scope constructor):
            The scope under which the remote server provides its methods.
        config (ParticipantConfig):
            The transport configuration that should be used for communication
            performed by this server.
        parent (Participant or NoneType):
            ``None`` or the :obj:`Participant` which should be considered the
            parent of the new server.

    Returns:
        rsb.patterns.RemoteServer:
            A newly created :obj:`RemoteServer` object.
    """
    import rsb.patterns as patterns
    return create_participant(patterns.RemoteServer, scope, config,
                              parent=parent, **kwargs)


def create_server(scope, config=None, parent=None,
                  provider=None, expose=None, methods=None,
                  **kwargs):
    """
    Like :obj:`create_local_server`.

    .. deprecated:: 0.12

       Use :obj:`create_local_server` instead.
    """
    return create_local_server(scope, config, parent,
                               provider=provider, expose=expose, methods=methods,
                               **kwargs)
