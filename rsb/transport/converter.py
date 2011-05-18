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

class Converter(object):
    """
    Base class for converters to a certain target type.

    @author: jwienke
    """

    def __init__(self, wireType, dataType, wireSchema):
        """
        Constructor.

        @param wireType: Python type to/from which the converter serializes/deserializes
        @param dataType: Python type of data accepted by the converter
                         for serialization (also Python type of
                         deserialized data)
        @param wireSchema: Wire-schema understood by the converter
                           when deserializing (also wire-schema of
                           data serialized with the converter)
        """
        self.__wireType = wireType
        self.__dataType = dataType
        self.__wireSchema = wireSchema

    def getWireType(self):
        '''
        Returns the type of the wire-type to/from this converter
        serializes/deserializes.

        @return A type object.
        '''
        return self.__wireType

    def getDataType(self):
        '''
        Returns the data type this converter is applicable for.

        @return A type object.
        '''
        return self.__dataType

    def getWireSchema(self):
        '''
        Returns the name of the wire schema this converter can
        (de)serialize from/to.

        @return A string designating the wire schema from/to this
                converter can (de)serialize
        '''
        return self.__wireSchema

    def serialize(self, input):
        raise NotImplementedError()

    def deserialize(self, input):
        raise NotImplementedError()

class UnknownConverterError(KeyError):
    """
    Raised if a converter for a target type is not available.

    @author: jwienke
    """

    def __init__(self, sourceType, wireSchema):
        KeyError.__init__(self, "No converter from type %s to type %s available" % (sourceType, wireSchema))

class ConverterMap(object):
    """
    A class managing converters for for a certain target type.

    @author: jwienke
    """

    def __init__(self, wireType):
        self.__wireType = wireType
        self.__converters = {}

    def getWireType(self):
        return self.__wireType

    def addConverter(self, converter, override=False):
        key = (converter.getWireSchema(), converter.getDataType())
        if key in self.__converters and not override:
            raise RuntimeError("There already is a converter with wire-schema `%s' and data-type `%s'"
                               % key)
        self.__converters[key] = converter

    def __getConverterForWireSchema(self, wireSchema):
        for ((converterWireSchema, ignored), converter) in self.__converters.items():
            if converterWireSchema == wireSchema:
                return converter

    def hasConverterForWireSchema(self, wireSchema):
        if self.__getConverterForWireSchema(wireSchema):
            return True
        else:
            return False

    def getConverterForWireSchema(self, wireSchema):
        converter = self.__getConverterForWireSchema(wireSchema)
        if converter:
            return converter
        raise KeyError, wireScheam

    def __getConverterForDataType(self, dataType):
        for ((ignored, converterDataType), converter) in self.__converters.items():
            if dataType is converterDataType:
                return converter

    def hasConverterForDataType(self, dataType):
        if self.__getConverterForDataType(dataType):
            return True
        else:
            return False

    def getConverterForDataType(self, dataType):
        converter = self.__getConverterForDataType(dataType)
        if converter:
            return converter
        raise KeyError, dataType

    def getConverters(self):
          return self.__converters

    def __str__(self):
        s = "ConverterMap(wireType = %s):\n" % self.__wireType
        for converter in self.__converters.values():
            s = s + ("\t%s <-> %s\n" % (converter.getWireSchema(), converter.getDataType()))
        return s[:-1]

class UnambiguousConverterMap (ConverterMap):
    def __init__(self, wireType):
        super(UnambiguousConverterMap, self).__init__(wireType)

    def addConverter(self, converter, override=False):
        for (wireSchema, dataType) in self.getConverters().keys():
            if wireSchema == converter.getWireSchema():
                if dataType == converter.getDataType():
                    super(UnambiguousConverterMap, self).addConverter(converter, override)
                else:
                    raise RuntimeError("Trying to register ambiguous converter with data type `%s' for wire-schema `%s' (present converter is for data type `%s')."
                                       % (converter.getDataType(), wireSchema, dataType))
        super(UnambiguousConverterMap, self).addConverter(converter, override)

__globalConverterMaps = {}

def registerGlobalConverter(converter, override=False):
    """
    Registers a new converter that s globally available to the system.

    @param converter: converter to register
    """
    if not converter.getWireType() in __globalConverterMaps:
        __globalConverterMaps[converter.getWireType()] = ConverterMap(converter.getWireType())
    __globalConverterMaps[converter.getWireType()].addConverter(converter, override)

def getGlobalConverterMap(targetType):
    """
    Get a map with all globally known converters for the desired target
    serialization type.

    @param targetType: python type for target serialization
    @return: converter map constantly updated
    """

    if not targetType in __globalConverterMaps:
        __globalConverterMaps[targetType] = ConverterMap(targetType)
    return __globalConverterMaps[targetType]

# --- converters with str as serialization type ---

class StringConverter(Converter):
    """
    An adapter to serialize strings to strings. ;)

    @author: jwienke
    """

    def __init__(self):
        Converter.__init__(self, wireType = str, wireSchema = "string", dataType = str)

    def serialize(self, input):
        return str(input)

    def deserialize(self, input):
        return str(input)

registerGlobalConverter(StringConverter())
