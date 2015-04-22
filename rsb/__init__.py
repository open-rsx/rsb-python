# ============================================================
#
# Copyright (C) 2010 by Johannes Wienke <jwienke at techfak dot uni-bielefeld dot de>
# Copyright (C) 2011, 2012, 2013, 2014 Jan Moringen <jmoringe@techfak.uni-bielefeld.de>
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

"""
This package contains all classes that form the high-level user interface of the
RSB python implementation. It is the entry point for most users and only in
advanced cases client programs need to use classes from other modules.

In order to create basic objects have a look at the functions L{createInformer},
L{createListener}, L{createServer} and L{createRemoteServer}.

@author: jwienke
@author: jmoringe
"""

import uuid
import copy
import logging
import threading
import time
import re
import os
import platform
import ConfigParser

from rsb.util import getLoggerByClass, Enum
import rsb.eventprocessing
import rsb.filter

_spreadAvailable = False
try:
    import spread
    _spreadAvailable = True
except ImportError:
    pass

def haveSpread():
    """
    Indicates whether the installation of RSB has spread support.

    @return: True if spread is available, else False
    """
    return _spreadAvailable

__defaultTransportsRegistered = False
__transportRegistrationLock = threading.RLock()
def __registerDefaultTransports():
    """
    Registers all available transports.
    """
    global __defaultTransportsRegistered
    with __transportRegistrationLock:
        if __defaultTransportsRegistered:
            return
        __defaultTransportsRegistered = True
        import rsb.transport.local
        rsb.transport.local.initialize()
        import rsb.transport.socket
        rsb.transport.socket.initialize()
        if haveSpread():
            import rsb.transport.rsbspread
            rsb.transport.rsbspread.initialize()

class QualityOfServiceSpec(object):
    """
    Specification of desired quality of service settings for sending
    and receiving events. Specification given here are required "at
    least". This means concrete connector implementations can provide
    "better" QoS specs without any notification to the clients. Better
    is decided by the integer value of the specification enums. Higher
    values mean better services.

    @author: jwienke
    """

    Ordering = Enum("Ordering", ["UNORDERED", "ORDERED"], [10, 20])
    Reliability = Enum("Reliability", ["UNRELIABLE", "RELIABLE"], [10, 20])

    def __init__(self, ordering=Ordering.UNORDERED, reliability=Reliability.RELIABLE):
        """
        Constructs a new QoS specification with desired
        details. Defaults are unordered but reliable.

        @param ordering: desired ordering type
        @param reliability: desired reliability type
        """
        self.__ordering = ordering
        self.__reliability = reliability

    def getOrdering(self):
        """
        Returns the desired ordering settings.

        @return: ordering settings
        """

        return self.__ordering

    def setOrdering(self, ordering):
        """
        Sets the desired ordering settings

        @param ordering: ordering to set
        """

        self.__ordering = ordering

    ordering = property(getOrdering, setOrdering)

    def getReliability(self):
        """
        Returns the desired reliability settings.

        @return: reliability settings
        """

        return self.__reliability

    def setReliability(self, reliability):
        """
        Sets the desired reliability settings

        @param reliability: reliability to set
        """

        self.__reliability = reliability

    reliability = property(getReliability, setReliability)

    def __eq__(self, other):
        try:
            return other.__reliability == self.__reliability and other.__ordering == self.__ordering
        except (AttributeError, TypeError):
            return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return "%s(%r, %r)" % (self.__class__.__name__, self.__ordering, self.__reliability)

def _configFileToDict(path, defaults={}):
    parser = ConfigParser.RawConfigParser()
    parser.read(path)
    options = defaults
    for section in parser.sections():
        for (k, v) in parser.items(section):
            options[section + '.' + k] = v.split('#')[0].strip()
    return options

def _configEnvironmentToDict(defaults={}):
    options = defaults
    for (key, value) in os.environ.items():
        if key.startswith('RSB_'):
            if value == '':
                raise ValueError, 'The value of the environment variable %s is the empty string' % key
            options[key[4:].lower().replace('_', '.')] = value
    return options

def _configDefaultSourcesToDict(defaults={}):
    """
    Obtain configuration options from multiple sources, store them
    in a L{ParticipantConfig} object and return it. The following
    sources of configuration information will be consulted:

     1. C{/etc/rsb.conf}
     2. C{$prefix/etc/rsb.conf}
     3. C{~/.config/rsb.conf}
     4. C{\$(PWD)/rsb.conf}
     5. Environment Variables

    @param defaults: dictionary with default options
    @type defaults: dict of str -> str
    @return: A dictionary object that contains the
             merged configuration options from the sources
             mentioned above.
    @rtype: dict of str -> str

    See also: L{_configFileToDict}, L{_configEnvironmentToDict}
    """

    import util

    if 'transport.socket.enabled' not in defaults:
        defaults['transport.socket.enabled'] = '1'
    if 'introspection.enabled' not in defaults:
        defaults['introspection.enabled'] = '1'
    if platform.system() == 'Windows':
        partial = _configFileToDict("c:\\rsb.conf", defaults)
    else:
        partial = _configFileToDict("/etc/rsb.conf", defaults)
    partial = _configFileToDict("%s/etc/rsb.conf" % util.prefix(), partial)
    partial = _configFileToDict(os.path.expanduser("~/.config/rsb.conf"), partial)
    partial = _configFileToDict("rsb.conf", partial)
    return _configEnvironmentToDict(partial)

_CONFIG_TRUE_VALUES = [ '1', 'true', 'yes' ]

def _configValueIsTrue(value):
    return value in _CONFIG_TRUE_VALUES

class ParticipantConfig (object):
    """
    Objects of this class describe desired configurations for newly
    created L{Participant}s with respect to:
     - Quality of service settings
     - Error handling strategies (not currently used)
     - Employed transport mechanisms
       - Their configurations (e.g. port numbers)
       - Associated converters
     - Whether introspection should be enabled for the participant
       (enabled by default)

    @author: jmoringe
    """

    class Transport (object):
        """
        Objects of this class describe configurations of transports
        connectors. These consist of
         - Transport name
         - Enabled vs. Disabled
         - Optional converter selection
         - Transport-specific options

        @author: jmoringe
        """
        def __init__(self, name, options={}, converters=None):
            self.__name = name
            self.__enabled = _configValueIsTrue(options.get('enabled', '0'))

            # Extract freestyle options for the transport.
            self.__options = dict([ (key, value) for (key, value) in options.items()
                                   if not '.' in key and not key == 'enabled' ])
            # Find converter selection rules
            self.__converters = converters
            self.__converterRules \
                = dict([ (key[len("converter.python."):], value) for (key, value) in options.items()
                         if key.startswith('converter.python') ])

        def getName(self):
            return self.__name

        name = property(getName)

        def isEnabled(self):
            return self.__enabled

        def setEnabled(self, flag):
            self.__enabled = flag

        enabled = property(isEnabled, setEnabled)

        def getConverters(self):
            return self.__converters

        def setConverters(self, converters):
            self.__converters = converters

        converters = property(getConverters, setConverters)

        def getConverterRules(self):
            return self.__converterRules

        def setConverterRules(self, converterRules):
            self.__converterRules = converterRules

        converterRules = property(getConverterRules, setConverterRules)

        def getOptions(self):
            return self.__options

        options = property(getOptions)

        def __deepcopy__(self, memo):
            result                  = copy.copy(self)
            result.__converters     = copy.deepcopy(self.__converters, memo)
            result.__converterRules = copy.deepcopy(self.__converterRules, memo)
            result.__options        = copy.deepcopy(self.__options, memo)
            return result

        def __str__(self):
            return ('ParticipantConfig.Transport[%s, enabled = %s, converters = %s, converterRules = %s, options = %s]'
                    % (self.__name, self.__enabled, self.__converters, self.__converterRules, self.__options))

        def __repr__(self):
            return str(self)

    def __init__(self,
                 transports    = None,
                 options       = None,
                 qos           = None,
                 introspection = False):
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

    def getTransports(self, includeDisabled=False):
        return [ t for t in self.__transports.values()
                 if includeDisabled or t.isEnabled() ]

    transports = property(getTransports)

    def getTransport(self, name):
        return self.__transports[name]

    def getQualityOfServiceSpec(self):
        return self.__qos

    def setQualityOfServiceSpec(self, newValue):
        self.__qos = newValue

    qualityOfServiceSpec = property(getQualityOfServiceSpec,
                                    setQualityOfServiceSpec)

    def getIntrospection(self):
        return self.__introspection

    def setIntrospection(self, newValue):
        self.__introspection = newValue

    introspection = property(getIntrospection, setIntrospection)

    def __deepcopy__(self, memo):
        result              = copy.copy(self)
        result.__transports = copy.deepcopy(self.__transports, memo)
        result.__options    = copy.deepcopy(self.__options, memo)
        return result

    def __str__(self):
        return 'ParticipantConfig[%s, options = %s, qos = %s, introspection = %s]' % (self.__transports.values(), self.__options, self.__qos, self.__introspection)

    def __repr__(self):
        return str(self)

    @classmethod
    def __fromDict(clazz, options):
        def sectionOptions(section):
            return [ (key[len(section) + 1:], value) for (key, value) in options.items()
                     if key.startswith(section) ]
        result = ParticipantConfig()

        # Quality of service
        qosOptions = dict(sectionOptions('qualityofservice'))
        result.__qos.setReliability(QualityOfServiceSpec.Reliability.fromString(qosOptions.get('reliability', QualityOfServiceSpec().getReliability().__str__())))
        result.__qos.setOrdering(QualityOfServiceSpec.Ordering.fromString(qosOptions.get('ordering', QualityOfServiceSpec().getOrdering().__str__())))

        # Transport options
        for transport in [ 'spread', 'socket', 'inprocess' ]:
            transportOptions = dict(sectionOptions('transport.%s' % transport))
            if transportOptions:
                result.__transports[transport] = clazz.Transport(transport, transportOptions)

        # Introspection options
        introspectionOptions = dict(sectionOptions('introspection'))
        result.__introspection = _configValueIsTrue(introspectionOptions.get('enabled', '1'))

        return result

    @classmethod
    def fromDict(clazz, options):
        return clazz.__fromDict(options)

    @classmethod
    def fromFile(clazz, path, defaults={}):
        """
        Obtain configuration options from the configuration file
        B{path}, store them in a L{ParticipantConfig} object and
        return it.

        A simple configuration file may look like this::

        [transport.spread]
        host = azurit # default type is string
        port = 5301 # types can be specified in angle brackets
        # A comment

        @param path: File of path
        @param defaults: dictionary with default options
        @type defaults: dict of str -> str
        @return: A new L{ParticipantConfig} object containing the
                 options read from B{path}.
        @rtype: ParticipantConfig

        See also: L{fromEnvironment}, L{fromDefaultSources}
        """
        return clazz.__fromDict(_configFileToDict(path, defaults))

    @classmethod
    def fromEnvironment(clazz, defaults={}):
        """
        Obtain configuration options from environment variables, store
        them in a L{ParticipantConfig} object and return
        it. Environment variable names are mapped to RSB option names
        as illustrated in the following example::

        RSB_TRANSPORT_SPREAD_PORT -> transport spread port

        @param defaults: dictionary with default options
        @type defaults: dict of str -> str
        @return: L{ParticipantConfig} object that contains the merged
                 configuration options from B{defaults} and relevant
                 environment variables.
        @rtype: ParticipantConfig

        See also: L{fromFile}, L{fromDefaultSources}
        """
        return clazz.__fromDict(_configEnvironmentToDict(defaults))

    @classmethod
    def fromDefaultSources(clazz, defaults={}):
        """
        Obtain configuration options from multiple sources, store them
        in a L{ParticipantConfig} object and return it. The following
        sources of configuration information will be consulted:

         1. C{/etc/rsb.conf}
         2. C{$prefix/etc/rsb.conf}
         3. C{~/.config/rsb.conf}
         4. C{\$(PWD)/rsb.conf}
         5. Environment Variables

        @param defaults: dictionary with default options
        @type defaults: dict of str -> str
        @return: A L{ParticipantConfig} object that contains the
                 merged configuration options from the sources
                 mentioned above.
        @rtype: ParticipantConfig

        See also: L{fromFile}, L{fromEnvironment}
        """

        return clazz.__fromDict(_configDefaultSourcesToDict(defaults))

def convertersFromTransportConfig(transport):
    """
    Returns an object implementing the
    L{rsb.converter.ConverterSelectionStrategy} protocol suitable for
    B{transport}.

    If C{transport.converters} is not C{None}, it is used
    unmodified. Otherwise the specification in
    C{transport.converterRules} is used.

    @return: The constructed ConverterSelectionStrategy object.
    @rtype: ConverterSelectionStrategy
    """

    # There are two possible ways to configure converters:
    # 1) transport.converters: this is either None or an object
    #    implementing the "ConverterSelectionStrategy protocol"
    # 2) when transport.converters is None, transport.converterRules
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
    wireType = bytearray

    import rsb
    import rsb.converter
    converterMap = rsb.converter.UnambiguousConverterMap(wireType)
    # Try to add converters form global map
    globalMap = rsb.converter.getGlobalConverterMap(wireType)
    for ((wireSchema, dataType), converter) in globalMap.getConverters().items():
        # Converter can be added if converterOptions does not
        # contain a disambiguation that gives precedence to a
        # different converter. map may still raise an
        # exception in case of ambiguity.
        if not wireSchema in transport.converterRules \
           or dataType.__name__ == transport.converterRules[wireSchema]:
            converterMap.addConverter(converter)
    return converterMap

class Scope(object):
    """
    A scope defines a channel of the hierarchical unified bus covered by RSB.
    It is defined by a surface syntax like C{"/a/deep/scope"}.

    @author: jwienke
    """

    __COMPONENT_SEPARATOR = "/"
    __COMPONENT_REGEX = re.compile("^[-_a-zA-Z0-9]+$")

    @classmethod
    def ensureScope(cls, thing):
        if isinstance(thing, cls):
            return thing
        else:
            return Scope(thing)

    def __init__(self, stringRep):
        """
        Parses a scope from a string representation.

        @param stringRep: string representation of the scope
        @type stringRep: str or unicode
        @raise ValueError: if B{stringRep} does not have the right
                           syntax
        """

        if len(stringRep) == 0:
            raise ValueError("The empty string does not designate a scope; Use '/' to designate the root scope.")

        if isinstance(stringRep, unicode):
            try:
                stringRep = stringRep.encode('ASCII')
            except UnicodeEncodeError, e:
                raise ValueError('Scope strings have be encodable as ASCII-strings, but the supplied scope string cannot be encoded as ASCII-string: %s'
                                 % e)

        # append missing trailing slash
        if stringRep[-1] != self.__COMPONENT_SEPARATOR:
            stringRep += self.__COMPONENT_SEPARATOR

        rawComponents = stringRep.split(self.__COMPONENT_SEPARATOR)
        if len(rawComponents) < 1:
            raise ValueError("Empty scope is not allowed.")
        if len(rawComponents[0]) != 0:
            raise ValueError("Scope must start with a slash. Given was '%s'." % stringRep)
        if len(rawComponents[-1]) != 0:
            raise ValueError("Scope must end with a slash. Given was '%s'." % stringRep)

        self.__components = rawComponents[1:-1]

        for com in self.__components:
            if not self.__COMPONENT_REGEX.match(com):
                raise ValueError("Invalid character in component %s. Given was scope '%s'." % (com, stringRep))

    def getComponents(self):
        """
        Returns all components of the scope as an ordered list. Components are
        the names between the separator character '/'. The first entry in the
        list is the highest level of hierarchy. The scope '/' returns an empty
        list.

        @return: components of the represented scope as ordered list with highest
                 level as first entry
        @rtype: list
        """
        return copy.copy(self.__components)

    components = property(getComponents)

    def toString(self):
        """
        Reconstructs a fully formal string representation of the scope with
        leading an trailing slashes.

        @return: string representation of the scope
        @rtype: str
        """

        string = self.__COMPONENT_SEPARATOR
        for com in self.__components:
            string += com
            string += self.__COMPONENT_SEPARATOR
        return string

    def concat(self, childScope):
        """
        Creates a new scope that is a sub-scope of this one with the
        subordinated scope described by the given
        argument. E.g. C{"/this/is/".concat("/a/test/")} results in
        C{"/this/is/a/test"}.

        @param childScope: child to concatenate to the current scope for forming a
                           sub-scope
        @type childScope: Scope
        @return: new scope instance representing the created sub-scope
        @rtype: Scope
        """
        newScope = Scope("/")
        newScope.__components = copy.copy(self.__components)
        newScope.__components += childScope.__components
        return newScope

    def isSubScopeOf(self, other):
        """
        Tests whether this scope is a sub-scope of the given other scope, which
        means that the other scope is a prefix of this scope. E.g. "/a/b/" is a
        sub-scope of "/a/".

        @param other: other scope to test
        @type other: Scope
        @return: C{True} if this is a sub-scope of the other scope, equality gives
                 C{False}, too
        @rtype: Bool
        """

        if len(self.__components) <= len(other.__components):
            return False

        return other.__components == self.__components[:len(other.__components)]

    def isSuperScopeOf(self, other):
        """
        Inverse operation of L{isSubScopeOf}.

        @param other: other scope to test
        @type other: Scope
        @return: C{True} if this scope is a strict super scope of the other scope.
                 equality also gives C{False}.
        @rtype: Bool
        """

        if len(self.__components) >= len(other.__components):
            return False

        return self.__components == other.__components[:len(self.__components)]

    def superScopes(self, includeSelf=False):
        """
        Generates all super scopes of this scope including the root
        scope "/".  The returned list of scopes is ordered by
        hierarchy with "/" being the first entry.

        @param includeSelf: if set to C{True}, this scope is also
                            included as last element of the returned
                            list

        @type includeSelf: Bool
        @return: list of all super scopes ordered by hierarchy, "/"
                 being first
        @rtype: list of Scopes
        """

        supers = []

        maxIndex = len(self.__components)
        if not includeSelf:
            maxIndex -= 1
        for i in range(maxIndex + 1):
            superScope = Scope("/")
            superScope.__components = self.__components[:i]
            supers.append(superScope)

        return supers

    def __eq__(self, other):
        return self.__components == other.__components

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.toString())

    def __lt__(self, other):
        return self.toString() < other.toString()

    def __le__(self, other):
        return self.toString() <= other.toString()

    def __gt__(self, other):
        return self.toString() > other.toString()

    def __ge__(self, other):
        return self.toString() >= other.toString()

    def __str__(self):
        return "Scope[%s]" % self.toString()

    def __repr__(self):
        return '%s("%s")' % (self.__class__.__name__, self.toString())

class MetaData (object):
    """
    Objects of this class store RSB-specific and user-supplied
    meta-data items such as timing information.

    @author: jmoringe
    """
    def __init__(self,
                 senderId=None,
                 createTime=None, sendTime=None, receiveTime=None, deliverTime=None,
                 userTimes=None, userInfos=None):
        """
        Constructs a new L{MetaData} object.

        @param createTime: A timestamp designating the time at which
                           the associated event was created.
        @param sendTime: A timestamp designating the time at which the
                         associated event was sent onto the bus.
        @param receiveTime: A timestamp designating the time at which
                            the associated event was received from the
                            bus.
        @param deliverTime: A timestamp designating the time at which
                            the associated event was delivered to the
                            user-level handler by RSB.
        @param userTimes: A dictionary of user-supplied timestamps.
        @type userTimes: dict from string name to double value as seconds since
                         unix epoche
        @param userInfos: A dictionary of user-supplied meta-data
                          items.
        @type userInfos: dict from string to string
        """
        if createTime is None:
            self.__createTime = time.time()
        else:
            self.__createTime = createTime
        self.__sendTime = sendTime
        self.__receiveTime = receiveTime
        self.__deliverTime = deliverTime
        if userTimes == None:
            self.__userTimes = {}
        else:
            self.__userTimes = userTimes
        if userInfos == None:
            self.__userInfos = {}
        else:
            self.__userInfos = userInfos

    def getCreateTime(self):
        return self.__createTime

    def setCreateTime(self, createTime=None):
        if createTime == None:
            self.__createTime = time.time()
        else:
            self.__createTime = createTime

    createTime = property(getCreateTime, setCreateTime)

    def getSendTime(self):
        return self.__sendTime

    def setSendTime(self, sendTime=None):
        if sendTime == None:
            self.__sendTime = time.time()
        else:
            self.__sendTime = sendTime

    sendTime = property(getSendTime, setSendTime)

    def getReceiveTime(self):
        return self.__receiveTime

    def setReceiveTime(self, receiveTime=None):
        if receiveTime == None:
            self.__receiveTime = time.time()
        else:
            self.__receiveTime = receiveTime

    receiveTime = property(getReceiveTime, setReceiveTime)

    def getDeliverTime(self):
        return self.__deliverTime

    def setDeliverTime(self, deliverTime=None):
        if deliverTime == None:
            self.__deliverTime = time.time()
        else:
            self.__deliverTime = deliverTime

    deliverTime = property(getDeliverTime, setDeliverTime)

    def getUserTimes(self):
        return self.__userTimes

    def setUserTimes(self, userTimes):
        self.__userTimes = userTimes

    def setUserTime(self, key, timestamp=None):
        if timestamp == None:
            self.__userTimes[key] = time.time()
        else:
            self.__userTimes[key] = timestamp

    userTimes = property(getUserTimes, setUserTimes)

    def getUserInfos(self):
        return self.__userInfos

    def setUserInfos(self, userInfos):
        self.__userInfos = userInfos

    def setUserInfo(self, key, value):
        self.__userInfos[key] = value

    userInfos = property(getUserInfos, setUserInfos)

    def __eq__(self, other):
        try:
            return (self.__createTime == other.__createTime) and (self.__sendTime == other.__sendTime) and (self.__receiveTime == other.__receiveTime) and (self.__deliverTime == other.__deliverTime) and (self.__userInfos == other.__userInfos) and (self.__userTimes == other.__userTimes)
        except (TypeError, AttributeError):
            return False

    def __neq__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return '%s[create = %s, send = %s, receive = %s, deliver = %s, userTimes = %s, userInfos = %s]' \
            % ('MetaData',
               self.__createTime, self.__sendTime, self.__receiveTime, self.__deliverTime,
               self.__userTimes, self.__userInfos)

    def __repr__(self):
        return self.__str__()

class EventId(object):
    """
    Uniquely identifies an Event by the sending participants ID and a sequence
    number within this participant. Optional conversion to uuid is possible.

    @author: jwienke
    """

    def __init__(self, participantId, sequenceNumber):
        self.__participantId = participantId
        self.__sequenceNumber = sequenceNumber
        self.__id = None

    def getParticipantId(self):
        """
        Return the sender id of this id.

        @return: sender id
        @rtype: uuid.UUID
        """
        return self.__participantId

    def setParticipantId(self, participantId):
        """
        Sets the participant id of this event.

        @param participantId: sender id to set.
        @type participantId: uuid.UUID
        """
        self.__participantId = participantId

    participantId = property(getParticipantId, setParticipantId)

    def getSequenceNumber(self):
        """
        Return the sequence number of this id.

        @return: sequence number of the id.
        @rtype: int
        """
        return self.__sequenceNumber

    def setSequenceNumber(self, sequenceNumber):
        """
        Sets the sequence number of this id.

        @param sequenceNumber: new sequence number of the id.
        @type sequenceNumber: int
        """
        self.__sequenceNumber = sequenceNumber

    sequenceNumber = property(getSequenceNumber, setSequenceNumber)

    def getAsUUID(self):
        """
        Returns a UUID encoded version of this id.

        @return: id of the event as UUID
        @rtype: uuid.uuid
        """

        if self.__id is None:
            self.__id = uuid.uuid5(self.__participantId,
                                   '%08x' % self.__sequenceNumber)
        return self.__id

    def __eq__(self, other):
        try:
            return (self.__sequenceNumber == other.__sequenceNumber) and (self.__participantId == other.__participantId)
        except (TypeError, AttributeError):
            return False

    def __neq__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return "EventId(%r, %r)" % (self.__participantId, self.__sequenceNumber)

    def __hash__(self):
        prime = 31;
        result = 1;
        result = prime * result + hash(self.__participantId)
        result = prime * result +  (self.__sequenceNumber ^ (self.__sequenceNumber >> 32))
        return result;

class Event(object):
    """
    Basic event class.

    Events are often caused by other events, which e.g. means that their
    contained payload was calculated on the payload of one or more other events.

    To express these relations each event contains a set of EventIds that express
    the direct causes of the event. This means, transitive event causes are not
    modeled.

    Cause handling is inspired by the ideas proposed in: David Luckham, The Power
    of Events, Addison-Wessley, 2007

    @author: jwienke
    """

    def __init__(self, id = None, scope = Scope("/"), method = None,
                 data = None, type = object,
                 metaData=None, userInfos=None, userTimes=None, causes = None):
        """
        Constructs a new event with undefined type, root scope and no data.

        @param id: The id of this event
        @type id: EventId
        @param scope: A L{Scope} designating the channel on which the
                      event will be published.
        @type scope: Scope or accepted by Scope constructor
        @param method: A string designating the "method category"
                       which identifies the role of the event in some
                       communication patters. Examples are
                       C{"REQUEST"} and C{"REPLY"}.
        @type method: str
        @param data: data contained in this event
        @param type: python data type of the contained data
        @type type: type
        @param metaData: meta data to use for the new event
        @type metaData: MetaData
        @param userInfos: key-value like store of user infos to add to the meta
                          data of this event
        @type userInfos: dict from string to string
        @param userTimes: additional timestamps to add to the meta data
        @type userTimes: dict from string timestamp name to value of timestamp
                         as dobule of seconds unix epoch
        @param causes: A list of L{EventId}s of events which causes the
                       newly constructed events.
        @type causes: list
        """

        self.__id = id
        self.__scope = Scope.ensureScope(scope)
        self.__method = method
        self.__data = data
        if type is None:
            raise ValueError("Type must not be None")
        self.__type = type
        if metaData is None:
            self.__metaData = MetaData()
        else:
            self.__metaData = metaData
        if not userInfos is None:
            for (key, value) in userInfos.items():
                self.__metaData.getUserInfos()[key] = value
        if not userTimes is None:
            for (key, value) in userTimes.items():
                self.__metaData.getUserTimes()[key] = value
        if not causes is None:
            self.__causes = copy.copy(causes)
        else:
            self.__causes = []

    def getSequenceNumber(self):
        """
        Return the sequence number of this event.

        @return: sequence number of the event.
        @rtype: int
        @deprecated: use #getId instead
        """
        return self.getId().getSequenceNumber()

    sequenceNumber = property(getSequenceNumber)

    def getId(self):
        """
        Returns the id of this event.

        @return: id of the event
        @rtype: int
        @raise RuntimeError: if the event does not have an id so far
        """

        if self.__id is None:
            raise RuntimeError("The event does not have an ID so far.")
        return self.__id

    def setId(self, theId):
        self.__id = theId

    id = property(getId, setId)

    def getScope(self):
        """
        Returns the scope of this event.

        @return: scope
        @rtype: Scope
        """

        return self.__scope

    def setScope(self, scope):
        """
        Sets the scope of this event.

        @param scope: scope to set
        @type scope: Scope
        """

        self.__scope = scope

    scope = property(getScope, setScope)

    def getSenderId(self):
        """
        Return the sender id of this event.

        @return: sender id
        @rtype: uuid.UUID
        @deprecated: use #getId instead
        """
        return self.getId().getParticipantId()

    senderId = property(getSenderId)

    def getMethod(self):
        """
        Return the method of this event.

        @return: A string designating the method of this event of
                 C{None} if this event does not have a method.
        """
        return self.__method

    def setMethod(self, method):
        """
        Sets the method of this event.

        @param method: The new method. C{None} is allowed.
        """
        self.__method = method

    method = property(getMethod, setMethod)

    def getData(self):
        """
        Returns the user data of this event.

        @return: user data
        """

        return self.__data

    def setData(self, data):
        """
        Sets the user data of this event

        @param data: user data
        """

        self.__data = data

    data = property(getData, setData)

    def getType(self):
        """
        Returns the type of the user data of this event.

        @return: user data type
        """

        return self.__type

    def setType(self, theType):
        """
        Sets the type of the user data of this event

        @param theType: user data type
        """

        self.__type = theType

    type = property(getType, setType)

    def getMetaData(self):
        return self.__metaData

    def setMetaData(self, metaData):
        self.__metaData = metaData

    metaData = property(getMetaData, setMetaData)

    def addCause(self, theId):
        """
        Adds a causing EventId to the causes of this event.

        @param theId: id to add
        @type theId: EventId
        @return: true if the id was newly added, else false
        @rtype: bool
        """
        if theId in self.__causes:
            return False
        else:
            self.__causes.append(theId)
            return True

    def removeCause(self, theId):
        """
        Removes a causing EventId from the causes of this event.

        @param theId: id to remove
        @type theId: EventId
        @return: true if the id was remove, else false (because it did not exist)
        @rtype: bool
        """
        if theId in self.__causes:
            self.__causes.remove(theId)
            return True
        else:
            return False

    def isCause(self, theId):
        """
        Checks whether a given id of an event is marked as a cause for this
        event.

        @param theId: id to check
        @type theId: EventId
        @return: true if the id is a cause of this event, else false
        @rtype: bool
        """
        return theId in self.__causes

    def getCauses(self):
        """
        Returns all causes of this event.

        @return: causing event ids
        @rtype: list of EventIds
        """
        return self.__causes

    def setCauses(self, causes):
        """
        Overwrites the cause vector of this event with the given one.

        @param causes: new cause vector
        @type causes: list of EventId
        """
        self.__causes = causes

    causes = property(getCauses, setCauses)

    def __str__(self):
        printData = str(self.__data)
        if len(printData) > 100:
            printData = printData[:100] + '...'
        printData = ''.join(['\\x%x' % ord(c) if ord(c) < 32 else c for c in printData])
        return "%s[id = %s, scope = '%s', data = '%s', type = '%s', method = '%s', metaData = %s, causes = %s]" \
            % ("Event", self.__id, self.__scope, printData, self.__type, self.__method, self.__metaData, self.__causes)

    def __repr__(self):
        return self.__str__()

    def __eq__(self, other):
        try:
            return (self.__id == other.__id) and (self.__scope == other.__scope) and (self.__type == other.__type) and (self.__data == other.__data) and (self.__metaData == other.__metaData) and (self.__causes == other.__causes)
        except (TypeError, AttributeError):
            return False

    def __neq__(self, other):
        return not self.__eq__(other)

class Hook (object):
    """
    A mutable collection of callback functions that can be called
    together.

    @author: jmoringe
    """

    def __init__(self):
        self.__lock     = threading.RLock()
        self.__handlers = []

    def run(self, *args, **kwargs):
        with self.__lock:
            for handler in self.__handlers:
                handler(*args, **kwargs)

    def addHandler(self, handler):
        with self.__lock:
            self.__handlers.append(handler)

    def removeHandler(self, handler):
        with self.__lock:
            self.__handlers.remove(handler)

participantCreationHook = Hook()

participantDestructionHook = Hook()

class Participant(object):
    """
    Base class for specialized bus participant classes. Has a unique
    id and a scope.

    @author: jmoringe
    """
    def __init__(self, scope, config):
        """
        Constructs a new Participant. This should not be done by
        clients.

        @param scope: scope of the bus channel.
        @type scope: Scope or accepted by Scope constructor

        @param config: Configuration that the participant should use
        @type config: ParticipantConfig

        See L{createListener}, L{createInformer}, L{createServer},
        L{createRemoteServer}
        """
        self.__id = uuid.uuid4()
        self.__scope = Scope.ensureScope(scope)
        self.__config = config

    def getId(self):
        return self.__id

    def setId(self, theId):
        self.__id = theId

    id = property(getId, setId)

    def getScope(self):
        return self.__scope

    def setScope(self, scope):
        self.__scope = scope

    scope = property(getScope, setScope)

    def getConfig(self):
        return self.__config

    config = property(getConfig)

    def activate(self):
        pass

    def deactivate(self):
        """
        Deactivates a participant by tearing down all connection
        logic. This needs to be called in case you want to ensure
        that programs can terminate correctly.
        """
        participantDestructionHook.run(self)

    def __enter__(self):
        return self

    def __exit__(self, execType, execValue, traceback):
        self.deactivate()

    @classmethod
    def getConnectors(clazz, direction, config):
        if not direction in ('in', 'out'):
            raise ValueError, 'Invalid direction: %s (valid directions are "in" and "out")' % direction
        if len(config.getTransports()) == 0:
            raise ValueError, 'No transports specified (config is %s)' \
                % config

        transports = []
        for transport in config.getTransports():
            factory = rsb.transport.getTransportFactory(transport.getName())
            converters = convertersFromTransportConfig(transport)
            if direction == 'in':
                transports.append(
                    factory.createInPushConnector(converters,
                                                  transport.getOptions()))
            elif direction == 'out':
                transports.append(
                    factory.createOutConnector(converters,
                                               transport.getOptions()))
            else:
                assert(False)
        return transports

class Informer(Participant):
    """
    Event-sending part of the communication pattern.

    @author: jwienke
    @author: jmoringe
    """

    def __init__(self, scope, config, dataType,
                 configurator = None):
        """
        Constructs a new L{Informer} that publishes L{Event}s carrying
        payloads of type B{type} on B{scope}.

        @param scope: scope of the informer
        @type scope: Scope or accepted by Scope constructor
        @param config: The configuration that should be used by this
                       L{Informer}.
        @type config: ParticipantConfig
        @param dataType: A Python object designating the type of
                         objects that will be sent via the new
                         L{Informer}. Instances of subtypes are
                         permitted as well.
        @type dataType: type
        @param configurator: Out route configurator to manage sending
                             of events through out connectors.
        @todo: maybe provide an automatic type identifier deduction for default
               types?
        @see: L{createInformer}
        """
        super(Informer, self).__init__(scope, config)

        self.__logger = getLoggerByClass(self.__class__)

        # TODO check that type can be converted
        if dataType is None:
            raise ValueError("dataType must not be None")
        self.__type           = dataType
        self.__sequenceNumber = 0
        self.__configurator   = None

        self.__active         = False
        self.__mutex          = threading.Lock()

        if configurator:
            self.__configurator = configurator
        else:
            connectors = self.getConnectors('out', config)
            for connector in connectors:
                connector.setQualityOfServiceSpec(config.getQualityOfServiceSpec())
            self.__configurator = rsb.eventprocessing.OutRouteConfigurator(connectors = connectors)
        self.__configurator.setQualityOfServiceSpec(config.getQualityOfServiceSpec())
        self.__configurator.scope = self.scope

        self.__activate()

    def __del__(self):
        self.__logger.debug("Destructing Informer")
        if self.__active:
            self.deactivate()

    def getType(self):
        """
        Returns the type of data sent by this informer.

        @return: type of sent data
        """
        return self.__type

    type = property(getType)

    def publishData(self, data, userInfos=None, userTimes=None):
        # TODO check activation
        self.__logger.debug("Publishing data '%s'", data)
        event = Event(scope = self.scope,
                      data = data, type = type(data),
                      userInfos = userInfos, userTimes = userTimes)
        return self.publishEvent(event)

    def publishEvent(self, event):
        """
        Publishes a predefined event. The caller must ensure that the
        event has the appropriate scope and type according to the
        L{Informer}'s settings.

        @param event: the event to send
        @type event: Event
        @rtype: Event
        """
        # TODO check activation

        if not event.scope == self.scope \
                and not event.scope.isSubScopeOf(self.scope):
            raise ValueError("Scope %s of event %s is not a sub-scope of this informer's scope %s."
                             % (event.scope, event, self.scope))
        if not isinstance(event.data, self.type):
            raise ValueError("The payload %s of event %s does not match this informer's type %s."
                             % (event.data, event, self.type))

        with self.__mutex:
            event.id = EventId(self.id, self.__sequenceNumber)
            self.__sequenceNumber += 1
        self.__logger.debug("Publishing event '%s'", event)
        self.__configurator.handle(event)
        return event

    def __activate(self):
        with self.__mutex:
            if self.__active:
                raise RuntimeError, "Activate called even though informer was already active"

            self.__logger.info("Activating informer")

            self.__configurator.activate()

            self.__active = True

        self.activate()

    def deactivate(self):
        with self.__mutex:
            if not self.__active:
                self.__logger.info("Deactivate called even though informer was not active")

            self.__logger.info("Deactivating informer")

            self.__active = False

            self.__configurator.deactivate()

        super(Informer, self).deactivate()

class Listener(Participant):
    """
    Event-receiving part of the communication pattern

    @author: jwienke
    @author: jmoringe
    """

    def __init__(self, scope, config,
                 configurator      = None,
                 receivingStrategy = None):
        """
        Create a new L{Listener} for B{scope}.

        @param scope: The scope of the channel in which the new
                      listener should participate.
        @type scope: Scopeor or accepted by Scope constructor
        @param config: The configuration that should be used by this
                        L{Listener}.
        @type config: ParticipantConfig
        @param configurator: An in route configurator to manage the
                             receiving of events from in connectors
                             and their filtering and dispatching.
        @see: L{createListener}
        """
        super(Listener, self).__init__(scope, config)

        self.__logger = getLoggerByClass(self.__class__)

        self.__filters      = []
        self.__handlers     = []
        self.__configurator = None
        self.__active       = False
        self.__mutex        = threading.Lock()

        if configurator:
            self.__configurator = configurator
        else:
            connectors = self.getConnectors('in', config)
            for connector in connectors:
                connector.setQualityOfServiceSpec(config.getQualityOfServiceSpec())
            self.__configurator = rsb.eventprocessing.InRouteConfigurator(connectors = connectors,
                                                                          receivingStrategy = receivingStrategy)
        self.__configurator.setScope(self.scope)

        self.__activate()

    def __del__(self):
        if self.__active:
            self.deactivate()

    def __activate(self):
        # TODO commonality with Informer... refactor
        with self.__mutex:
            if self.__active:
                raise RuntimeError, "Activate called even though listener was already active"

            self.__logger.info("Activating listener")

            self.__configurator.activate()

            self.__active = True

        self.activate()

    def deactivate(self):
        with self.__mutex:
            if not self.__active:
                raise RuntimeError, "Deactivate called even though listener was not active"

            self.__logger.info("Deactivating listener")

            self.__configurator.deactivate()

            self.__active = False

        super(Listener, self).deactivate()

    def addFilter(self, theFilter):
        """
        Appends a filter to restrict the events received by this listener.

        @param filter: filter to add
        """

        with self.__mutex:
            self.__filters.append(theFilter)
            self.__configurator.filterAdded(theFilter)

    def getFilters(self):
        """
        Returns all registered filters of this listener.

        @return: list of filters
        """

        with self.__mutex:
            return list(self.__filters)

    def addHandler(self, handler, wait=True):
        """
        Adds B{handler} to the list of handlers this listener invokes
        for received events.

        @param handler: Handler to add. callable with one argument,
                        the event.
        @param wait: If set to C{True}, this method will return only
                     after the handler has completely been installed
                     and will receive the next available
                     message. Otherwise it may return earlier.
        """

        with self.__mutex:
            if not handler in self.__handlers:
                self.__handlers.append(handler)
                self.__configurator.handlerAdded(handler, wait)

    def removeHandler(self, handler, wait=True):
        """
        Removes B{handler} from the list of handlers this listener
        invokes for received events.

        @param handler: Handler to remove.
        @param wait: If set to C{True}, this method will return only
                     after the handler has been completely removed
                     from the event processing and will not be called
                     anymore from this listener.
        """

        with self.__mutex:
            if handler in self.__handlers:
                self.__configurator.handlerRemoved(handler, wait)
                self.__handlers.remove(handler)

    def getHandlers(self):
        """
        Returns the list of all registered handlers.

        @return: list of handlers to execute on matches
        @rtype: list of callables accepting an L{Event}.
        """
        with self.__mutex:
            return list(self.__handlers)

__defaultConfigurationOptions = _configDefaultSourcesToDict()
__defaultParticipantConfig = ParticipantConfig.fromDict(__defaultConfigurationOptions)

def getDefaultParticipantConfig():
    """
    Returns the current default configuration for new objects.
    """
    return __defaultParticipantConfig

def setDefaultParticipantConfig(config):
    """
    Replaces the default configuration for new objects.

    @param config: A ParticipantConfig object which contains the new defaults.
    """
    global __defaultParticipantConfig
    __defaultParticipantConfig = config

_introspectionDisplayName = __defaultConfigurationOptions.get('introspection.displayname')
_introspectionInitialized = False
_introspectionMutex = threading.RLock()

def _initializeIntrospection():
    global _introspectionInitialized
    import rsb.introspection
    with _introspectionMutex:
        if not _introspectionInitialized:
            rsb.introspection.initialize(_introspectionDisplayName)
            _introspectionInitialized = True

def createParticipant(clazz, scope, config, parent = None, **kwargs):
    if config is None:
        config = getDefaultParticipantConfig()
    __registerDefaultTransports()

    if config.introspection:
        _initializeIntrospection()

    participant = clazz(scope, config = config, **kwargs)
    participantCreationHook.run(participant, parent = parent)
    return participant

def createListener(scope, config = None, parent = None, **kwargs):
    """
    Creates and returns a new L{Listener} for B{scope}.

    @param scope: the scope of the new L{Listener}. Can be a L{Scope} object or a string.
    @type scope: Scope or accepted by L{Scope} constructor
    @param config: The configuration that should be used by this
                   L{Listener}.
    @type config: ParticipantConfig
    @param parent: C{None} or the L{Participant} which should be
                   considered the parent of the new L{Listener}.
    @type  parent: Participant or NoneType
    @return: a new L{Listener} object.
    """
    return createParticipant(Listener, scope, config, parent,
                             **kwargs)

def createInformer(scope, config = None, parent = None, dataType = object,
                   **kwargs):
    """
    Creates and returns a new L{Informer} for B{scope}.

    @param scope: The scope of the new L{Informer}. Can be a L{Scope}
                  object or a string.
    @type scope: Scope or accepted by L{Scope} constructor
    @param config: The configuration that should be used by this
                   L{Informer}.
    @type config: ParticipantConfig
    @param parent: C{None} or the L{Participant} which should be
                   considered the parent of the new L{Informer}.
    @type  parent: Participant or NoneType
    @param dataType: A Python object designating the type of
                     objects that will be sent via the new
                     L{Informer}. Instances of subtypes are
                     permitted as well.
    @type dataType: type
    @return: a new L{Informer} object.
    """
    return createParticipant(Informer, scope, config, parent,
                             dataType = dataType,
                             **kwargs)

def createLocalServer(scope, config = None, parent = None,
                      object = None, expose = None, methods = None,
                      **kwargs):
    """
    Create and return a new L{LocalServer} object that exposes its
    methods under B{scope}.

    The keyword parameters object, expose and methods can be used to
    associate an initial set of methods with the newly created server
    object.

    @param scope: The scope under which the newly created server
                  should expose its methods.
    @type scope: Scope or accepted by L{Scope} constructor
    @param config: The configuration that should be used by this
                   server.
    @type config: ParticipantConfig
    @param parent: C{None} or the L{Participant} which should be
                   considered the parent of the new server.
    @type  parent: Participant or NoneType
    @param object: An object the methods of which should be exposed
                   via the newly created server. Has to be supplied in
                   combination with the expose keyword parameter.
    @param expose: A list of names of attributes of object that should
                   be expose as methods of the newly created
                   server. Has to be supplied in combination with the
                   object keyword parameter.
    @param methods: A list or tuple of lists or tuples of the length four:
                    a method name,
                    a callable implementing the method,
                    a type designating the request type of the method and
                    a type designating the reply type of the method.
    @return: A newly created L{LocalServer} object.
    @rtype: rsb.patterns.LocalServer
    """
    # Check arguments
    if not object is None and not expose is None and not methods is None:
        raise ValueError, 'Supply either object and expose or methods'
    if object is None and not expose is None \
            or not object is None and expose is None:
        raise ValueError, 'object and expose have to supplied together'

    # Create the server object and potentially add methods.
    import rsb.patterns
    server = createParticipant(rsb.patterns.LocalServer,
                               scope, config, parent,
                               **kwargs)
    if object and expose:
        methods = [ (name, getattr(object, name), requestType, replyType)
                    for (name, requestType, replyType) in expose ]
    if methods:
        for (name, func, requestType, replyType) in methods:
            server.addMethod(name, func, requestType, replyType)
    return server

def createRemoteServer(scope, config = None, parent = None, **kwargs):
    """
    Create a new L{RemoteServer} object for a remote server that
    provides its methods under B{scope}.

    @param scope: The scope under which the remote server provides its
                  methods.
    @type scope: Scope or accepted by Scope constructor
    @return: A newly created L{RemoteServer} object.
    @param config: The transport configuration that should be used
                   for communication performed by this server.
    @type config: ParticipantConfig
    @param parent: C{None} or the L{Participant} which should be
                   considered the parent of the new server.
    @type  parent: Participant or NoneType
    @rtype: rsb.patterns.RemoteServer
    """
    import rsb.patterns
    return createParticipant(rsb.patterns.RemoteServer, scope, config,
                             **kwargs)

def createServer(scope, config = None, parent = None,
                 object = None, expose = None, methods = None,
                 **kwargs):

    """
    Like L{createLocalServer}.

    @deprecated: Use L{createLocalServer} instead.
    """
    return createLocalServer(scope, config, parent,
                             object = object, expose = expose, methods = methods,
                             **kwargs)
