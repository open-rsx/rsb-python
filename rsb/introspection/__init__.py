# ============================================================
#
# Copyright (C) 2014 Jan Moringen <jmoringe@techfak.uni-bielefeld.de>
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
This package contains partial introspection functionality for RSB.

The introspection functionality is implemented in terms of RSB events
and thus built on top of "ordinary" RSB communication.

This package implements the "local introspection" (i.e. introspection
sender) part of the introspection architecture.

@author: jmoringe
"""

import sys
import os

import uuid

import rsb
from rsb.util import getLoggerByClass
import rsb.converter

from rsb.protocol.introspection.Hello_pb2 import Hello
from rsb.protocol.introspection.Bye_pb2 import Bye

# Register converters for introspection messages

for clazz in [ Hello, Bye ]:
    converter = rsb.converter.ProtocolBufferConverter(messageClass = clazz)
    rsb.converter.registerGlobalConverter(converter, replaceExisting = True)

# Model

class ParticipantInfo (object):
    """
    Instances of this class store information about a participant.

    The participant can reside in the current process or in a remote
    process.

    @author: jmoringe
    """

    def __init__(self, kind, id, scope, type, parentId = None):
        self.__kind  = kind
        self.__id    = id
        self.__scope = rsb.Scope.ensureScope(scope)
        self.__type  = type
        self.__parentId = parentId

    def getKind(self):
        """
        Returns the kind of the participant.

        Examples include "listener", "informer" and "local-server".

        @return: A lower-case, hyphen-separated string identifying the
                 kind of participant.
        @rtype: str
        """
        return self.__kind

    kind = property(getKind)

    def getId(self):
        """
        Returns the unique id of the participant.

        @return: The unique id of the participant.
        @rtype: uuid.uuid
        """
        return self.__id

    id = property(getId)

    def getScope(self):
        """
        Returns the scope of the participant.

        @return: The scope of the participant.
        @rtype: rsb.Scope
        """
        return self.__scope

    scope = property(getScope)

    def getType(self):
        """
        Returns a representation of the type of the participant, if
        available.

        Note that this is a temporary solution and will change in
        future versions.

        @return: A representation of the type.
        @rtype: type or tuple
        """
        return self.__type

    type = property(getType)

    def getParentId(self):
        """
        Return the unique id of the parent participant of the participant,
        or C{None}, if the participant does not have a parent.

        @return: C{None} or the unique id of the participant's parent.
        @rtype: uuid.uuid or NoneType
        """
        return self.__parentId

    parentId = property(getParentId)

    def __str__(self):
        return '<%s %s %s at 0x%0x>' \
            % (type(self).__name__, self.kind, self.scope.toString(), id(self))

    def __repr__(self):
        return str(self)

__processStartTime = None

def processStartTime():
    """
    Return the start time of the current process (or an approximation)
    in fractional seconds since UNIX epoch.

    @return: Start time in factional seconds since UNIX epoch.
    @rtype: float
    """
    global __processStartTime

    # Used cached value, if there is one.
    if not __processStartTime is None:
        return __processStartTime

    # Try to determine the start time of the current process in a
    # platform dependent way. Since all of these methods seem kind of
    # error prone, allow failing silently and fall back to the default
    # implementation below.
    if 'linux' in sys.platform:
        try:
            import re

            procStatContent = open('/proc/stat').read()
            btimeEntry = re.match('(?:.|\n)*btime ([0-9]+)', procStatContent).group(1)
            bootTimeUNIXSeconds = int(btimeEntry)

            selfStatContent = open('/proc/self/stat').read()
            startTimeBootJiffies = int(selfStatContent.split(' ')[21])

            __processStartTime = (  float(bootTimeUNIXSeconds)
                                  + float(startTimeBootJiffies) / 100.0)
        except:
            pass

    # Default/fallback strategy: just use the current time.
    if __processStartTime is None:
        import time
        __processStartTime = time.time()

    return __processStartTime

class ProcessInfo (object):
    """
    Instances of this class store information about operating system
    processes.

    The stored information can describe the current process, a
    different process on the local machine or a remote process.

    @author: jmoringe
    """

    def __init__(self,
                 id          = os.getpid(),
                 programName = ('python%d.%d %s'
                                % (sys.version_info.major,
                                   sys.version_info.minor,
                                   sys.argv[0] or '<stdin>')), # TODO construct absolute path
                 arguments   = sys.argv[1:],
                 startTime   = processStartTime()):
        self.__id          = id
        self.__programName = programName
        self.__arguments   = arguments
        self.__startTime   = startTime

    def getId(self):
        """
        Returns the numeric id of the process.

        @return: The numeric id of the process.
        @rtype: int
        """
        return self.__id

    id = property(getId)

    def getProgramName(self):
        """
        Returns the name of the program being executed in the process.

        @return: The name of the program.
        @rtype: str
        """
        return self.__programName

    programName = property(getProgramName)

    def getArguments(self):
        """
        Returns the list of commandline argument the process has been
        started with.

        @return: A list of commandline argument strings
        @rtype: list
        """
        return self.__arguments

    arguments = property(getArguments)

    def getStartTime(self):
        """
        Returns the start time of the process in fractional seconds
        since UNIX epoch.

        @return: start time in fractional seconds since UNIX epoch.
        @rtype: float
        """
        return self.__startTime

    startTime = property(getStartTime)

    def __str__(self):
        return '<%s %s [%d] at 0x%0x>' \
            % (type(self).__name__, self.programName, self.id, id(self))

    def __repr__(self):
        return str(self)

def hostId():
    """
    Returns a unique id string for the current host.

    @return: A platform-dependent, string (hopefully) uniquely
             identifying the current host or C{None} if such an id
             cannot be obtained.
    @rtype: str or NoneType
    """
    def maybeRead(filename):
        try:
            with open(filename, 'r') as f:
                return f.read().strip()
        except:
            return None

    return ('linux' in sys.platform and maybeRead('/var/lib/dbus/machine-id')) \
        or ('linux' in sys.platform and maybeRead('/ect/machine-id'))          \
        or None

class HostInfo (object):
    """
    Instances of this class store information about a host.

    The stored information can describe the local host or a remote
    host.

    @author: jmoringe
    """

    def __init__(self,
                 id       = hostId(),
                 hostname = os.uname()[1]): # TODO no os.gethostname(); whatever
        self.__id       = id
        self.__hostname = hostname

    def getId(self):
        """
        Return the unique id string for the host.

        @return: The platform-dependent, (hopefully) unique id string.
        @rtype: str or None
        """
        return self.__id

    id = property(getId)

    def getHostname(self):
        """
        Returns the hostname of the host.

        @return: The hostname
        @rtype: str
        """
        return self.__hostname

    hostname = property(getHostname)

    def __str__(self):
        return '<%s %s at 0x%0x>' % (type(self).__name__, self.hostname, id(self))

    def __repr__(self):
        return str(self)

# IntrospectionSender

baseScope         = rsb.Scope('/__rsb/introspection/')
participantsScope = baseScope.concat(rsb.Scope('/participants/'))
hostsScope        = baseScope.concat(rsb.Scope('/hosts/'))

def participantScope(participantId, baseScope = participantsScope):
    return baseScope.concat(rsb.Scope('/' + str(participantId)))

def processScope(hostId, processId, baseScope = hostsScope):
    return (baseScope
            .concat(rsb.Scope('/' + hostId))
            .concat(rsb.Scope('/' + processId)))

class IntrospectionSender (object):
    """
    Instances of this class (usually zero or one per process) send
    information about participants in the current process, the current
    process itself and the local host to receivers of introspection
    information.

    Instances need to be notified of created and destroyed
    participants via calls of the L{addParticipant} and
    L{removeParticipant} methods.

    @author: jmoringe
    """

    def __init__(self):
        self.__logger = getLoggerByClass(self.__class__)

        self.__participants = []

        self.__process = ProcessInfo()
        self.__host    = HostInfo()

        self.__informer = rsb.createInformer(participantsScope)
        self.__listener = rsb.createListener(participantsScope)
        def handle(event):
            if not event.method in [ 'REQUEST', 'SURVEY' ]: # TODO use filter when we get conjunction filter
                return

            id          = None
            participant = None
            if len(event.scope.components) > len(participantsScope.components):
                try:
                    id = uuid.UUID(event.scope.components[-1])
                    if not id is None:
                        for p in self.__participants: # TODO there has to be a better way
                            if p.id == id:
                                participant = p
                            break
                except Exception, e:
                    self.__logger.warn('Query event %s does not properly address a participant: %s',
                                       event, e)

            def process(thunk):
                if not participant is None and event.method == 'REQUEST':
                    thunk(query = event, participant = participant)
                elif participant is None and event.method == 'SURVEY':
                    map(lambda p: thunk(query = event, participant = p),
                        self.__participants)
                else:
                    self.__logger.warn('Query event %s not understood' % event)

            if event.data is None:
                process(self.sendHello)
            elif event.data == 'ping':
                process(self.sendPong)
            else:
                self.__logger.warn('Query event %s not understood' % event)

        self.__listener.addHandler(handle)

        self.__server = rsb.createServer(processScope(self.__host.id,
                                                      str(self.__process.id)))
        def echo(event):
            metaData = event.metaData
            metaData.setUserTime('request.send',    metaData.sendTime)
            metaData.setUserTime('request.receive', metaData.receiveTime)
            return event
        self.__server.addMethod('echo', echo,
                                requestType = rsb.Event,
                                replyType   = rsb.Event)

    def deactivate(self):
        self.__listener.deactivate()
        self.__informer.deactivate()
        self.__server.deactivate()

    def getProcess(self):
        return self.__process

    process = property(getProcess)

    def getHost(self):
        return self.__host

    host = property(getHost)

    def addParticipant(self, participant, parent = None):
        parentId = None
        if parent:
            parentId = parent.id
        info = ParticipantInfo(kind     = type(participant).__name__,
                               id       = participant.id,
                               parentId = parentId,
                               scope    = participant.scope,
                               type     = object) # TODO

        self.__participants.append(info)

        self.sendHello(info)

    def removeParticipant(self, participant):
        removed = None
        for p in self.__participants:
            if p.id == participant.id:
                removed = p
                break

        if not removed is None:
            self.__participants.remove(removed)
            self.sendBye(removed)

        return bool(self.__participants)

    def sendHello(self, participant, query = None):
        hello = Hello()
        hello.kind  = participant.kind.lower()
        hello.id    = participant.id.get_bytes()
        hello.scope = participant.scope.toString()
        if participant.parentId:
            hello.parent = participant.parentId.get_bytes()

        host = hello.host
        if not self.host.id is None:
            host.id = self.host.id
        host.hostname = self.host.hostname

        process = hello.process
        process.id           = str(self.process.id)
        process.program_name = self.process.programName
        map(process.commandline_arguments.append, self.process.arguments)
        process.start_time   = int(self.process.startTime * 1000000.0)

        scope = participantScope(participant.id, self.__informer.scope)
        helloEvent = rsb.Event(scope = scope,
                               data  = hello,
                               type  = type(hello))
        if query:
            helloEvent.addCause(query.id)
        self.__informer.publishEvent(helloEvent)

    def sendBye(self, participant):
        bye = Bye()
        bye.id = participant.id.get_bytes()

        scope = participantScope(participant.id, self.__informer.scope)
        byeEvent = rsb.Event(scope = scope,
                             data  = bye,
                             type  = type(bye))
        self.__informer.publishEvent(byeEvent)

    def sendPong(self, participant, query = None):
        scope = participantScope(participant.id, self.__informer.scope)
        pongEvent = rsb.Event(scope = scope,
                              data  = 'pong',
                              type  = str)
        if query:
            pongEvent.addCause(query.id)
        self.__informer.publishEvent(pongEvent)

__sender = None

def handleParticipantCreation(participant, parent = None):
    """
    This function is intended to be connected to
    L{rsb.participantCreationHook} and calls
    L{IntrospectionSender.addParticipant} when appropriate, first
    creating the L{IntrospectionSender} instance, if necessary.
    """
    global __sender

    if participant.scope.isSubScopeOf(baseScope) \
       or not participant.config.introspection:
        return

    if __sender is None:
        __sender = IntrospectionSender()
    __sender.addParticipant(participant, parent = parent)

rsb.participantCreationHook.addHandler(handleParticipantCreation)

def handleParticipantDestruction(participant):
    """
    This function is intended to be connected to
    L{rsb.participantDestructionHook} and calls
    L{IntrospectionSender.removeParticipant} when appropriate,
    potentially deleting the L{IntrospectionSender} instance
    afterwards.
    """
    global __sender

    if participant.scope.isSubScopeOf(baseScope) \
       or not participant.config.introspection:
        return

    if __sender and not __sender.removeParticipant(participant):
        __sender.deactivate()
        __sender = None

rsb.participantDestructionHook.addHandler(handleParticipantDestruction)
