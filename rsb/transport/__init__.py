# ============================================================
#
# Copyright (C) 2010 by Johannes Wienke <jwienke at techfak dot uni-bielefeld dot de>
# Copyright (C) 2011, 2012 Jan Moringen <jmoringe@techfak.uni-bielefeld.de>
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
This module contains different transport implementations for RSB and their
common base classes and utility functions.

@author: jmoringe
@author: jwienke
"""

import copy
import threading

from rsb.util import getLoggerByClass
import logging

class Connector(object):
    """
    Superclass for transport-specific connector classes.

    @author: jwienke
    """

    def __init__(self, wireType = None, **kwargs):
        """
        Creates a new connector with a serialization type wireType.

        @param wireType: the type of serialized data used by this
                         connector.
        @type wireType: type
        """
        self.__logger = getLoggerByClass(self.__class__)

        self.__wireType = None
        self.__scope    = None

        if wireType == None:
            raise ValueError("Wire type must be a type object, None given")

        self.__logger.debug("Using specified converter map for wire-type %s" % wireType)
        self.__wireType = wireType

        # fails if still some arguments are left over
        super(Connector, self).__init__(**kwargs)

    def getWireType(self):
        """
        Returns the serialization type used for this connector.

        @return: python serialization type
        """
        return self.__wireType

    wireType = property(getWireType)

    def getScope(self):
        return self.__scope

    def setScope(self, newValue):
        """
        Sets the scope this connector will receive events from to
        B{newValue}. Called before #activate.

        @param newValue: scope of the connector
        @type newValue: rsb.Scope
        """
        self.__scope = newValue

    scope = property(getScope, setScope)

    def activate(self):
        raise NotImplementedError()

    def deactivate(self):
        raise NotImplementedError()

    def setQualityOfServiceSpec(self, qos):
        raise NotImplementedError()

class InConnector(Connector):
    """
    Superclass for in-direction (that is, dealing with incoming
    events) connector implementations.

    @author: jmoringe
    """

    def filterNotify(self, filter, action):
        raise NotImplementedError()

    def setObserverAction(self, action):
        """
        Sets the action used by the connector to notify about incoming
        events. The call to this method must be thread-safe.

        @param action: action called if a new message is received from
        the connector. Must accept an L{Event} as parameter.
        """
        pass

class OutConnector(Connector):
    """
    Superclass for out-direction (that is, dealing with outgoing
    events) connector implementations.

    @author: jmoringe
    """

    def handle(self, event):
        """
        Sends B{event} and adapts its meta data instance with the
        actual send time.

        @param event: event to send
        """
        raise NotImplementedError()

class ConverterSelectingConnector (object):
    """
    This class is intended to be used a superclass (or rather mixin
    class) for connector classes which have to store a map of
    converters and select converters for (de)serialization.

    @author: jmoringe
    """

    def __init__(self, converters, **kwargs):
        """
        Creates a new connector that uses the converters in
        B{converters} to deserialize notification and/or serialize
        events.

        @param converters: The converter selection strategy that
                           should be used by the connector. If
                           C{None}, the global map of converters for
                           the wire-type of the connector is used.
        @type converters: rsb.converter.ConverterSelectionStrategy
        """
        self.__converterMap = converters

        assert(self.__converterMap.getWireType() == self.wireType)

    def getConverterForDataType(self, dataType):
        """
        Returns a converter that can convert the supplied data to the
        wire-type.

        @param dataType: the type of the object for which a suitable
                         converter should returned.
        @return: converter
        @raise KeyError: no converter is available for the supplied
                         data.
        """
        return self.__converterMap.getConverterForDataType(dataType)

    def getConverterForWireSchema(self, wireSchema):
        """
        Returns a suitable converter for the B{wireSchema}.

        @param wireSchema: the wire-schema to or from which the
                           returned converter should convert
        @type wireSchema: str
        @return: converter
        @raise KeyError: no converter is available for the specified
                         wire-schema.
        """
        return self.__converterMap.getConverterForWireSchema(wireSchema)

    def getConverterMap(self):
        return self.__converterMap

    converterMap = property(getConverterMap)

__connectors = []
__connectorsLock = threading.Lock()

def getConnectors():
    with __connectorsLock:
        return copy.copy(__connectors)

def addConnector(clazz):
    with __connectorsLock:
        __connectors.append(clazz)
