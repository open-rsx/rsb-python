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

import logging

import rsb.filter
import converter

from Queue import Queue, Empty
from rsb import EventProcessor, util
from rsb.util import getLoggerByClass
from threading import RLock

class Router(object):
    """
    Routers to publish and subscribe on events.

    @author: jwienke
    """

    def __init__(self, inPort=None, outPort=None, eventProcessor=None):
        """
        Creates a new router.

        @param inPort: port for ingoing communication or None for no port
        @param outPort: port for outgoing communication or None for no port
        @param eventProcessor: event processor to use
        """

        self.__logger = getLoggerByClass(self.__class__)

        self.__logger.debug("Creating router with inPort = %s, outPort = %s and eventProcessor = %s" % (inPort, outPort, eventProcessor))

        if inPort:
            self.__inPort = inPort
            self.__eventProcessor = eventProcessor
            if self.__eventProcessor == None:
                self.__eventProcessor = EventProcessor()
            self.__inPort.setObserverAction(self.__eventProcessor.process)
        else:
            self.__inPort = None
            self.__eventProcessor = None
        if outPort:
            self.__outPort = outPort
        else:
            self.__outPort = None

        self.__active = False

    def __del__(self):
        self.__logger.debug("Destructing router")
        if self.__active:
            self.deactivate()

    def setQualityOfServiceSpec(self, qos):
        if self.__inPort:
            self.__inPort.setQualityOfServiceSpec(qos)
        if self.__outPort:
            self.__outPort.setQualityOfServiceSpec(qos)

    def activate(self):
        if not self.__active:
            self.__logger.info("Activating router")
            if self.__inPort:
                self.__inPort.activate()
            if self.__outPort:
                self.__outPort.activate()
            self.__active = True
        else:
            self.__logger.warning("Router was already activated")

    def deactivate(self):
        if self.__active:
            self.__logger.info("Deactivating router")
            if self.__inPort:
                self.__inPort.deactivate()
                self.__inPort.setObserverAction(None)
                self.__eventProcessor.deactivate()
            if self.__outPort:
                self.__outPort.deactivate()
            self.__active = False
        else:
            self.__logger.warning("Router was not active")

    def publish(self, event):
        if self.__active and self.__outPort:
            self.__logger.debug("Publishing event: %s" % event)
            self.__outPort.push(event)
        else:
            self.__logger.warning("Router is not active or has no outgoing port. Cannot publish.")

    def __notifyPorts(self, subscription, filterAction):
        if self.__inPort:
            for f in subscription.getFilters():
                self.__inPort.filterNotify(f, filterAction)

    def subscribe(self, subscription):
        self.__logger.debug("New subscription %s" % subscription)
        self.__notifyPorts(subscription, rsb.filter.FilterAction.ADD)
        if self.__eventProcessor:
            self.__eventProcessor.subscribe(subscription)

    def unsubscribe(self, subscription):
        self.__logger.debug("Remove subscription %s" % subscription)
        self.__notifyPorts(subscription, rsb.filter.FilterAction.REMOVE)
        if self.__eventProcessor:
            self.__eventProcessor.unsubscribe(subscription)

class Port(object):
    """
    Interface for transport-specific ports.

    @author: jwienke
    """

    def __init__(self, wireType, converterMap=None):
        """
        Creates a new port with a serialization type wireType.

        @param wireType: the type of serialized data used by this port.
        @param converterMap: map of converters to use. If None, the global
                             map of converters for the selected targetType is
                             used
        """

        self.__logger = getLoggerByClass(self.__class__)

        if wireType == None:
            raise ValueError("Wire type must be a class or primitive type, None given")

        if converterMap == None:
            self.__logger.debug("Using global converter map for wire-type %s" % wireType)
            self.__converterMap = converter.getGlobalConverterMap(wireType)
        else:
            self.__logger.debug("Using specified converter map for wire-type %s" % wireType)
            self.__converterMap = converterMap
        assert(self.__converterMap.getWireType() == wireType)
        self.__wireType = wireType

    def getWireType(self):
        """
        Returns the serialization type used for this port.

        @return: python serialization type
        """
        return self.__wireType

    def _getConverterForDataType(self, dataType):
        """
        Returns a converter that can convert the supplied data to the
        wire-type.

        @param dataType: the type of the object for which a suitable
                         converter should returned.
        @return: converter
        @raise KeyError: no converter is available for the supplied data.
        """
        #self.__logger.debug("Searching for converter for data '%s' in map %s" % (data, self.__converterMap))
        return self.__converterMap.getConverterForDataType(dataType)

    def _getConverterForWireSchema(self, wireSchema):
        """
        Returns the converter for the wire-schema.

        @param wireSchema: the wire-schema to or from which the returned converter should convert
        @return: converter
        @raise KeyError: no converter is available for the specified wire-schema
        """
        self.__logger.debug("Searching for converter with wireSchema '%s' in map %s" % (wireSchema, self.__converterMap))
        return self.__converterMap.getConverterForWireSchema(wireSchema)

    def _getConverterMap(self):
        return self.__converterMap

    def activate(self):
        raise NotImplementedError()
    def deactivate(self):
        raise NotImplementedError()
    def publish(self, event):
        raise NotImplementedError()
    def filterNotify(self, filter, action):
        raise NotImplementedError()
    def setQualityOfServiceSpec(self, qos):
        raise NotImplementedError()

    def setObserverAction(self, observerAction):
        """
        Sets the action used by the port to notify about incomming events.
        The call to this method must be thread-safe.

        @param observerAction: action called if a new message is received from
                               the port. Must accept an RSBEvent as parameter.
        """
        pass
