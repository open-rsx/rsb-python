# ============================================================
#
# Copyright (C) 2010 by Johannes Wienke <jwienke at techfak dot uni-bielefeld dot de>
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

import uuid
import copy
import logging
import threading
from rsb.util import getLoggerByClass, OrderedQueueDispatcherPool, Enum
import re
import os
import ConfigParser

class QualityOfServiceSpec(object):
    '''
    Specification of desired quality of service settings for sending and
    receiving events. Specification given here are required "at least". This
    means concrete port instances can implement "better" QoS specs without any
    notification to the clients. Better is decided by the integer value of the
    specification enums. Higher values mean better services.
    
    @author: jwienke
    '''

    Ordering = Enum("Ordering", ["UNORDERED", "ORDERED"], [10, 20])
    Reliability = Enum("Reliability", ["UNRELIABLE", "RELIABLE"], [10, 20])

    def __init__(self, ordering=Ordering.UNORDERED, reliability=Reliability.RELIABLE):
        '''
        Constructs a new QoS specification with desired details. Defaults are
        unordered but reliable.
        
        @param ordering: desired ordering type
        @param reliability: desired reliability type
        '''
        self.__ordering = ordering
        self.__reliability = reliability

    def getOrdering(self):
        '''
        Returns the desired ordering settings.
        
        @return: ordering settings
        '''

        return self.__ordering

    def setOrdering(self, ordering):
        '''
        Sets the desired ordering settings
        
        @param ordering: ordering to set
        '''

        self.__ordering = ordering

    ordering = property(getOrdering, setOrdering)

    def getReliability(self):
        '''
        Returns the desired reliability settings.
        
        @return: reliability settings
        '''

        return self.__reliability

    def setReliability(self, reliability):
        '''
        Sets the desired reliability settings
        
        @param reliability: reliability to set
        '''

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

class ParticipantConfig (object):
    '''
    @author: jmoringe
    '''
    
    class Transport (object):
        def __init__(self, name, options={}):
            self.__name = name
            self.__enabled = options.get('enabled', '1') == 1
            self.__options = dict([ (key, value) for (key, value) in options.items()
                                   if not '.' in key and not key == 'enabled' ])

        def getOptions(self):
            return self.__options

        def __str__(self):
            return ('ParticipantConfig.Transport[%s, enabled = %s,  %s]'
                    % (self.__name, self.__enabled, self.__options))

        def __repr__(self):
            return str(self)

    def __init__(self, transports={}, options={}, qos = QualityOfServiceSpec()):
        self.__transports = transports
        self.__options = options
        self.__qos = qos

    def getTransport(self, name):
        return self.__transports[name]
    
    def getQualityOfServiceSpec(self):
        return self.__qos

    def __str__(self):
        return 'ParticipantConfig[%s %s]' % (self.__transports.values(), self.__options)

    def __repr__(self):
        return str(self)

    @classmethod
    def __fromDict(clazz, options):
        def sectionOptions(section):
            return [ (key[len(section) + 1:], value) for (key, value) in options.items()
                     if key.startswith(section) ]
        result = ParticipantConfig()
        for transport in [ 'spread' ]:
            options = dict(sectionOptions('transport.%s' % transport))
            result.__transports[transport] = clazz.Transport(transport, options)
        return result

    @classmethod
    def __fromFile(clazz, path, defaults={}):
        parser = ConfigParser.RawConfigParser()
        parser.read(path)
        options = defaults
        for section in parser.sections():
            for (k, v) in parser.items(section):
                options[section + '.' + k] = v
        return options

    @classmethod
    def fromFile(clazz, path, defaults={}):
        '''
        Obtain configuration options from the configuration file @a
        path, store them in a @ref ParticipantConfig object and return
        it.

        A simple configuration file may look like this:
        @verbatim
        [transport.spread]
        host = azurit # default type is string
        port = 5301 # types can be specified in angle brackets
        # A comment
        @endverbatim

        @param path File of path
        @param defaults  defaults
        @return

        @see fromEnvironment, fromDefaultSources
        '''
        return clazz.__fromDict(clazz.__fromFile(path, defaults))

    @classmethod
    def __fromEnvironment(clazz, defaults={}):
        options = defaults
        for (key, value) in os.environ.items():
            if key.startswith('RSB_'):
                options[key[4:].lower().replace('_', '.')] = value
        return options

    @classmethod
    def fromEnvironment(clazz, defaults={}):
        '''
        Obtain configuration options from environment variables, store
        them in a @ref ParticipantConfig object and return
        it. Environment variable names are mapped to RSB option names
        as illustrated in the following example:

        @verbatim
        RSB_TRANSPORT_SPREAD_PORT -> transport spread port
        @endverbatim

        @param defaults A @ref ParticipantConfig object that supplies
        values for configuration options for which no environment
        variables are found.
        @return A @ref ParticipantConfig object that contains the
        merged configuration options from @a defaults and relevant
        environment variables.

        @see fromFile, fromDefaultSources
        '''
        return clazz.__fromDict(clazz.__fromEnvironment(defaults))

    @classmethod
    def fromDefaultSources(clazz, defaults={}):
        '''
        Obtain configuration options from multiple sources, store
        them in a @ref ParticipantConfig object and return it. The
        following sources of configuration information will be
        consulted:
        
        -# ~/.config/rsb.conf
        -# \$(PWD)/rsb.conf
        -# Environment Variables
        
        @param defaults A @ref ParticipantConfig object the options
        of which should be used as defaults.
        
        @return A @ref ParticipantConfig object that contains the
        merged configuration options from the sources mentioned
        above.
        
        @see fromFile, fromEnvironment
        '''
        partial = clazz.__fromFile(os.path.expanduser("~/.config/rsb.conf"))
        partial = clazz.__fromFile("rsb.conf", partial)
        options = clazz.__fromEnvironment(partial)
        return clazz.__fromDict(options)

class Scope(object):
    '''
    A scope defines a channel of the hierarchical unified bus covered by RSB.
    It is defined by a surface syntax like "/a/deep/scope".

    @author: jwienke
    '''

    __COMPONENT_SEPARATOR = "/"
    __COMPONENT_REGEX = re.compile("^[a-zA-Z0-9]+$")

    def __init__(self, stringRep):
        '''
        Parses a scope from a string representation.

        @param stringRep: string representation of the scope
        @raise ValueError: if the given string does not have the right syntax
        '''

        if len(stringRep) == 0:
            raise ValueError("Empty scope is invalid.")

        # append missing trailing slash
        if stringRep[-1] != self.__COMPONENT_SEPARATOR:
            stringRep += self.__COMPONENT_SEPARATOR

        rawComponents = stringRep.split('/')
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
        '''
        Returns all components of the scope as an ordered list. Components are
        the names between the separator character '/'. The first entry in the
        list is the highest level of hierarchy. The scope '/' returns an empty
        list.

        @return: components of the represented scope as ordered list with highest
                 level as first entry
        @rtype: list
        '''
        return copy.copy(self.__components)

    def toString(self):
        '''
        Reconstructs a fully formal string representation of the scope with
        leading an trailing slashes.

        @return: string representation of the scope
        @rtype: string
        '''

        string = self.__COMPONENT_SEPARATOR
        for com in self.__components:
            string += com
            string += self.__COMPONENT_SEPARATOR
        return string

    def concat(self, childScope):
        '''
        Creates a new scope that is a sub-scope of this one with the subordinated
        scope described by the given argument. E.g. "/this/is/".concat("/a/test/")
        results in "/this/is/a/test".

        @param: childScope child to concatenate to the current scope for forming a
                           sub-scope
        @type childScope: Scope
        @return: new scope instance representing the created sub-scope
        @rtype: Scope
        '''
        newScope = Scope("/")
        newScope.__components = copy.copy(self.__components)
        newScope.__components += childScope.__components
        return newScope

    def isSubScopeOf(self, other):
        '''
        Tests whether this scope is a sub-scope of the given other scope, which
        means that the other scope is a prefix of this scope. E.g. "/a/b/" is a
        sub-scope of "/a/".

        @param other: other scope to test
        @type other: Scope
        @return: @c true if this is a sub-scope of the other scope, equality gives
                @c false, too
        @rtype: Bool
        '''

        if len(self.__components) <= len(other.__components):
            return False

        return other.__components == self.__components[:len(other.__components)]

    def isSuperScopeOf(self, other):
        '''
        Inverse operation of #isSubScopeOf.

        @param other: other scope to test
        @type other: Scope
        @return: @c true if this scope is a strict super scope of the other scope.
                 equality also gives @c false.
        @rtype: Bool
        '''

        if len(self.__components) >= len(other.__components):
            return False

        return self.__components == other.__components[:len(self.__components)]

    def superScopes(self, includeSelf=False):
        '''
        Generates all super scopes of this scope including the root scope "/".
        The returned list of scopes is ordered by hierarchy with "/" being the
        first entry.

        @param includeSelf: if set to @true, this scope is also included as last
                            element of the returned list
        @type includeSelf: Bool
        @return: list of all super scopes ordered by hierarchy, "/" being first
        @rtype: list of Scopes
        '''

        supers = []

        maxIndex = len(self.__components)
        if not includeSelf:
            maxIndex -= 1
        for i in range(maxIndex + 1):
            super = Scope("/")
            super.__components = self.__components[:i]
            supers.append(super)

        return supers

    def __eq__(self, other):
        return self.__components == other.__components

    def __ne__(self, other):
        return not self.__eq__(other)

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

class RSBEvent(object):
    '''
    Basic event class.

    @author: jwienke
    '''

    def __init__(self):
        """
        Constructs a new event with undefined type, root scope and no data.
        The uuid is randomly generated.
        """

        self.__uuid = uuid.uuid1()
        self.__scope = Scope("/")
        self.__data = None
        self.__type = None

    def getUUID(self):
        """
        Returns the uuid of this event.

        @return: uuid id of the event
        """

        return self.__uuid

    def setUUID(self, uuid):
        """
        Sets the uuid of the event.

        @param uuid: uuid to set
        """

        self.__uuid = uuid

    uuid = property(getUUID, setUUID)

    def getScope(self):
        """
        Returns the scope of this event.

        @return: scope
        """

        return self.__scope

    def setScope(self, scope):
        """
        Sets the scope of this event.

        @param scope: scope to set
        """

        self.__scope = scope

    scope = property(getScope, setScope)

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

    def setType(self, type):
        """
        Sets the type of the user data of this event

        @param type: user data type
        """

        self.__type = type

    type = property(getType, setType)

    def __str__(self):
        printData = self.__data
        if isinstance(self.__data, str) and len(self.__data) > 10000:
            printData = "string with length %u" % len(self.__data)
        return "%s[uuid = %s, scope = '%s', data = '%s', type = '%s']" % ("RSBEvent", self.__uuid, self.__scope, printData, self.__type)

    def __eq__(self, other):
        try:
            return (self.__uuid == other.__uuid) and (self.__scope == other.__scope) and (self.__type == other.__type) and (self.__data == other.__data)
        except (TypeError, AttributeError):
            return False

    def __neq__(self, other):
        return not self.__eq__(other)

class Subscription(object):
    """
    A subscription in the RSB system. A subscription can be restricted by
    actions and additional filter for the matching process.

    @author: jwienke
    """

    def __init__(self):
        """
        Creates a new subscription that does not match anything.
        """

        self.__filters = []
        self.__actions = []
        self.__logger = getLoggerByClass(self.__class__)

    def appendFilter(self, filter):
        """
        Appends a filter to restrict this subscription.

        @param filter: filter to add
        """

        self.__filters.append(filter)

    def getFilters(self):
        """
        Returns all registered filters of this subscription.

        @return: list of filters
        """

        return self.__filters

    def appendAction(self, action):
        """
        Appends an action this subscription shall match on.

        @param action: action to append. callable with one argument, the
                       RSBEvent
        """

        if not action in self.__actions:
            self.__actions.append(action)

    def getActions(self):
        """
        Returns the list of all registered actions.

        @return: list of actions to execute on matches
        @rtype: list of callables accepting an RSBEvent
        """
        return self.__actions

    def match(self, event):
        """
        Matches this subscription against the provided event.

        @param event: event to match against
        @rtype: bool
        @return: True if the subscription accepts the event, else False
        """

        for filter in self.__filters:
            if not filter.match(event):
                self.__logger.debug("Filter %s filter did not match event %s" % (filter, event))
                return False

        self.__logger.debug("All filters matched event %s " % event)
        return True

    def __str__(self):
        return "Subscription[filters = %s, actions = %s]" % (self.__filters, self.__actions)

class EventProcessor(object):
    """
    @author: jwienke
    """

    def __init__(self, numThreads=5):
        self.__logger = getLoggerByClass(self.__class__)
        self.__pool = OrderedQueueDispatcherPool(threadPoolSize=numThreads, delFunc=EventProcessor.__deliver, filterFunc=EventProcessor.__filter)
        self.__pool.start()

    def __del__(self):
        self.__logger.debug("Destructing EventProcesor")
        self.deactivate()

    def deactivate(self):
        self.__logger.debug("Deactivating EventProcesor")
        if self.__pool:
            self.__pool.stop()
            self.__pool = None

    @classmethod
    def __deliver(cls, subscription, event):
        for action in subscription.getActions():
            action(event)

    @classmethod
    def __filter(cls, subscription, event):
        return subscription.match(event)

    def process(self, event):
        """
        Dispatches the event to all registered subscribers.

        @type event: RSBEvent
        @param event: event to dispatch
        """
        self.__logger.debug("Processing event %s" % event)
        self.__pool.push(event)

    def subscribe(self, subscription):
        """
        Subscribe on selected actions.

        @type subscription: Subscription
        @param subscription: the subscription to add
        """
        self.__logger.debug("Subscription added %s" % subscription)
        self.__pool.registerReceiver(subscription)

    def unsubscribe(self, subscription):
        """
        Unsubscribe.

        @type subscription: Subscription
        @param subscription: subscription to remove
        """
        self.__logger.debug("Subscription removed %s" % subscription)
        self.__pool.unregisterReceiver(subscription)

class Publisher(object):
    """
    Event-sending part of the communication pattern.

    @author: jwienke
    """

    def __init__(self, scope, type,
                 config=ParticipantConfig.fromDefaultSources(),
                 router=None):
        """
        Constructs a new Publisher.

        @param scope: scope of the publisher
        @param router: router object with open outgoing port for communication
        @param type: type identifier string
        @todo: maybe provide an automatic type identifier deduction for default
               types?
        """
        from rsbspread import SpreadPort
        from transport import Router

        self.__logger = getLoggerByClass(self.__class__)

        self.__scope = scope
        if router:
            self.__router = router
        else:
            self.__router = Router(outPort=SpreadPort(options=config.getTransport('spread').getOptions()))
        self.__router.setQualityOfServiceSpec(config.getQualityOfServiceSpec())
        # TODO check that type can be converted
        self.__type = type

        self.__active = False
        self.__mutex = threading.Lock()

        self.activate()

    def __del__(self):
        self.__logger.debug("Destructing Publisher")
        self.deactivate()

    def publishData(self, data):
        # TODO check activation
        self.__logger.debug("Publishing data '%s'" % data)
        event = RSBEvent()
        event.setData(data)
        event.setType(self.__type)
        self.publishEvent(event)

    def publishEvent(self, event):
        # TODO check activation
        # TODO check that type is available and suitable
        event.setScope(self.__scope)
        self.__logger.debug("Publishing event '%s'" % event)
        self.__router.publish(event)

    def activate(self):
        with self.__mutex:
            if not self.__active:
                self.__router.activate()
                self.__active = True
                self.__logger.info("Activated publisher")
            else:
                self.__logger.info("Activate called even though publisher was already active")

    def deactivate(self):
        with self.__mutex:
            if self.__active:
                self.__router.deactivate()
                self.__active = False
                self.__logger.info("Deactivated publisher")
            else:
                self.__logger.info("Deactivate called even though publisher was not active")

class Subscriber(object):
    """
    Event-receiving part of the communication pattern

    @author: jwienke
    """

    def __init__(self, scope,
                 config=ParticipantConfig.fromDefaultSources(),
                 router=None):
        """
        Create a new subscriber for the specified scope.

        @todo: why the duplicated scope, also passed in using the scope filter?
        @param scope: scope to subscribe one
        @param router: router with existing inport
        """
        from rsbspread import SpreadPort
        from transport import Router

        self.__logger = getLoggerByClass(self.__class__)

        self.__scope = scope
        if router:
            self.__router = router
        else:
            self.__router = Router(inPort=SpreadPort(options=config.getTransport('spread').getOptions()))


        self.__mutex = threading.Lock()
        self.__active = False

        self.activate()

    def __del__(self):
        self.deactivate()

    def activate(self):
        # TODO commonality with Publisher... refactor
        with self.__mutex:
            if not self.__active:
                self.__router.activate()
                self.__active = True
                self.__logger.info("Activated subscriber")
            else:
                self.__logger.info("Activate called even though subscriber was already active")

    def deactivate(self):
        with self.__mutex:
            if self.__active:
                self.__router.deactivate()
                self.__active = False
                self.__logger.info("Deactivated subscriber")
            else:
                self.__logger.info("Deactivate called even though subscriber was not active")

    def addSubscription(self, subscription):
        self.__logger.debug("New subscription %s" % subscription)
        self.__router.subscribe(subscription)

    def removeSubscription(self, subscription):
        self.__logger("Removing subscription %s" % subscription)
        self.__router.unsubscribe(subscription)
