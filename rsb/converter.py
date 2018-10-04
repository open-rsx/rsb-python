# ============================================================
#
# Copyright (C) 2010 by Johannes Wienke <jwienke at techfak dot uni-bielefeld dot de>
# Copyright (C) 2011-2017 Jan Moringen <jmoringe@techfak.uni-bielefeld.de>
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
A module containing various converter implementations as well as logic for
registering and selecting them.

.. codeauthor:: jmoringe
.. codeauthor:: jwienke
.. codeauthor:: plueckin
"""

import abc
from numbers import Integral, Real
import struct
from threading import RLock

from rsb import Scope
from rsb.protocol.collections.EventsByScopeMap_pb2 import EventsByScopeMap
from rsb.transport.conversion import (event_to_notification,
                                      notification_to_event)


class Converter(object):
    """
    Base class for converters to a certain target type.

    .. codeauthor:: jwienke
    """

    def __init__(self, wire_type, data_type, wire_schema):
        """
        Constructor.

        Args:
            wire_type (types.TypeType):
                Python type to/from which the converter serializes/deserializes
            data_type (types.TypeType):
                Python type of data accepted by the converter for serialization
                (also Python type of deserialized data)
            wire_schema (str):
                Wire-schema understood by the converter when deserializing
                (also wire-schema of data serialized with the converter)
        """
        self.__wire_type = wire_type
        self.__data_type = data_type
        self.__wire_schema = wire_schema

    def get_wire_type(self):
        """
        Returns the type of the wire-type to/from this converter
        serializes/deserializes.

        Returns:
            types.TypeType:
                A type object.
        """
        return self.__wire_type

    wire_type = property(get_wire_type)

    def get_data_type(self):
        """
        Returns the data type this converter is applicable for.

        Returns:
            types.TypeType:
                A type object.
        """
        return self.__data_type

    data_type = property(get_data_type)

    def get_wire_schema(self):
        """
        Returns the name of the wire schema this converter can (de)serialize
        from/to.

        Returns:
            str:
                A string designating the wire schema from/to this converter can
                (de)serialize
        """
        return self.__wire_schema

    wire_schema = property(get_wire_schema)

    def serialize(self, inp):
        raise NotImplementedError()

    def deserialize(self, inp, wire_schema):
        raise NotImplementedError()


class UnknownConverterError(KeyError):
    """
    .. codeauthor:: jwienke
    """

    def __init__(self, source_type, wire_schema):
        KeyError.__init__(
            self,
            "No converter from type %s to type %s available" % (source_type,
                                                                wire_schema))


class ConverterSelectionStrategy(object):
    """
    This class defines the interface for converter selection strategy
    classes.

    .. codeauthor:: jmoringe
    """

    def has_converter_for_wire_schema(self, wire_schema):
        return bool(self._get_converter_for_wire_schema(wire_schema))

    def get_converter_for_wire_schema(self, wire_schema):
        converter = self._get_converter_for_wire_schema(wire_schema)
        if converter:
            return converter
        raise KeyError(wire_schema)

    def has_converter_for_data_type(self, data_type):
        return bool(self._get_converter_for_data_type(data_type))

    def get_converter_for_data_type(self, data_type):
        converter = self._get_converter_for_data_type(data_type)
        if converter:
            return converter
        raise KeyError(data_type)

    @abc.abstractmethod
    def _get_converter_for_wire_schema(self, wire_schma):
        pass

    @abc.abstractmethod
    def _get_converter_for_data_type(self, data_type):
        pass


class ConverterMap(ConverterSelectionStrategy):
    """
    A class managing converters for for a certain target type.

    .. codeauthor:: jwienke
    """

    def __init__(self, wire_type):
        self._wire_type = wire_type
        self._converters = {}

    def get_wire_type(self):
        return self._wire_type

    def add_converter(self, converter, replace_existing=False):
        key = (converter.get_wire_schema(), converter.get_data_type())
        if key in self._converters and not replace_existing:
            raise RuntimeError("There already is a converter "
                               "with wire-schema `%s' and data-type `%s'"
                               % key)
        self._converters[key] = converter

    def _get_converter_for_wire_schema(self, wire_schema):
        for ((converter_wire_schema, _), converter) in list(self._converters.items()):
            if converter_wire_schema == wire_schema:
                return converter

    def _get_converter_for_data_type(self, data_type):
        # If multiple converters are applicable, use most specific.
        candidates = []
        for ((_, converter_data_type), converter) in list(self._converters.items()):
            if issubclass(data_type, converter_data_type):
                candidates.append(converter)
        if len(candidates) == 1:
            return candidates[0]
        elif len(candidates) > 1:
            def compare_via_subclass(x, y):
                if issubclass(x.get_data_type(), y.get_data_type()):
                    return -1
                else:
                    return 1

            def cmp_to_key(mycmp):
                'Convert a cmp= function into a key= function'
                class K:
                    def __init__(self, obj, *args):
                        self.obj = obj

                    def __lt__(self, other):
                        return mycmp(self.obj, other.obj) < 0

                    def __gt__(self, other):
                        return mycmp(self.obj, other.obj) > 0

                    def __eq__(self, other):
                        return mycmp(self.obj, other.obj) == 0

                    def __le__(self, other):
                        return mycmp(self.obj, other.obj) <= 0

                    def __ge__(self, other):
                        return mycmp(self.obj, other.obj) >= 0

                    def __ne__(self, other):
                        return mycmp(self.obj, other.obj) != 0
                return K
            return sorted(candidates,
                          key=cmp_to_key(compare_via_subclass))[0]

    def get_converters(self):
        return self._converters

    def __str__(self):
        s = "ConverterMap(wire_type = %s):\n" % self._wire_type
        for converter in list(self._converters.values()):
            s = s + ("\t%s <-> %s\n" % (converter.get_wire_schema(),
                                        converter.get_data_type()))
        return s[:-1]


class PredicateConverterList(ConverterMap):
    """
    Objects of this class are used to perform converter selection via
    a chain-of-responsibility strategy.

    A list of predicates and associated converters is
    maintained. Converter selection queries are processed by
    traversing the list and selected the first converter the
    associated predicate of which matches the query wire-schema or
    data-type.

    .. codeauthor:: jmoringe
    """

    def __init__(self, wire_type):
        super(PredicateConverterList, self).__init__(wire_type)
        self._list = []

    def add_converter(self, converter,
                      wire_schema_predicate=None,
                      data_type_predicate=None,
                      replace_existing=True):
        if wire_schema_predicate is None:
            # if converter.get_wire_schema() == 'void':
            #    wire_schema_predicate = lambda wire_schema: True
            # else:
            def wire_schema_predicate(wire_schema): return \
                wire_schema == converter.get_wire_schema()
        if data_type_predicate is None:
            def data_type_predicate(data_type): return \
                data_type == converter.get_data_type()
        key = (wire_schema_predicate, data_type_predicate)
        self._converters[key] = converter
        self._list.append((key, converter))

    def _get_converter_for_wire_schema(self, wire_schema):
        for ((predicate, _), converter) in self._list:
            if predicate(wire_schema):
                return converter

    def _get_converter_for_data_type(self, data_type):
        for ((_, predicate), converter) in self._list:
            if predicate(data_type):
                return converter


class UnambiguousConverterMap(ConverterMap):
    def __init__(self, wire_type):
        super(UnambiguousConverterMap, self).__init__(wire_type)

    def add_converter(self, converter, replace_existing=False):
        for (wire_schema, data_type) in list(self.get_converters().keys()):
            if wire_schema == converter.get_wire_schema() \
               and not data_type == converter.get_data_type():
                raise RuntimeError(
                    "Trying to register ambiguous converter "
                    "with data type `%s' for wire-schema `%s' "
                    "(present converter is for data type `%s')."
                    % (converter.get_data_type(),
                       wire_schema,
                       data_type))
        super(UnambiguousConverterMap, self).add_converter(
            converter, replace_existing)


__global_converter_maps_lock = RLock()
__global_converter_maps = {}


def register_global_converter(converter, replace_existing=False):
    """
    Register ``converter`` as a globally available converter.

    Args:
        converter:
            converter to register
        replace_existing:
            controls whether an existing converter for the same data-type
            and/or wire-type should be replaced by the new converter. If this
            is ``False`` and such a converter exists, an error is raised.
    """
    map_for_wire_type = get_global_converter_map(converter.get_wire_type())
    map_for_wire_type.add_converter(converter, replace_existing)


def get_global_converter_map(wire_type):
    """
    Get a map with all globally known converters for the ``wire_type``.

    Args:
        wire_type (types.TypeType):
            Python type for designating the wire-type.

    Returns:
        converter map constantly updated
    """

    with __global_converter_maps_lock:
        if wire_type not in __global_converter_maps:
            __global_converter_maps[wire_type] = ConverterMap(wire_type)
        return __global_converter_maps[wire_type]

# --- converters with bytes as serialization type ---


class IdentityConverter(Converter):
    """
    This converter does nothing. Use it in combination with the
    "always_applicable"-wire_schema.

    .. codeauthor:: plueckin
    """

    def __init__(self):
        super(IdentityConverter, self).__init__(bytes, type(None), 'void')

    def serialize(self, inp):
        return bytes(), self.wire_schema

    def deserialize(self, inp, wire_schema):
        pass

    def always_applicable(self):
        return bytes


class NoneConverter(Converter):
    """
    This converter produces a serialized value that represents
    instances of ``NoneType``.

    Such a converter is required for serializing "results" of RPC
    calls that do not return a value.

    .. codeauthor:: jmoringe
    """

    def __init__(self):
        super(NoneConverter, self).__init__(bytes, type(None), 'void')

    def serialize(self, inp):
        return bytes(), self.wire_schema

    def deserialize(self, inp, wire_schema):
        assert wire_schema == self.wire_schema


def make_struct_based_converter(name, data_type, wire_schema, fmt, size):
    class NewConverter(Converter):
        def __init__(self):
            super(self.__class__, self).__init__(
                bytes, data_type, wire_schema)

        def serialize(self, inp):
            return bytes(struct.pack(fmt, inp)), self.wire_schema

        def deserialize(self, inp, wire_schema):
            assert wire_schema == self.wire_schema
            return struct.unpack(fmt, inp)[0]

    NewConverter.__name__ = name
    # TODO(jmoringe): seems to be impossible in CPython
    # NewConverter.__doc__ = """
    # A converter that serializes %(data_type)s to bytes with
    # %(wire_schema)s wire-schema.
    #
    # .. codeauthor:: jmoringe
    # """ % {
    #     "data_type":   data_type,
    #     "wire_schema": wire_schema
    # }

    globals()[name] = NewConverter
    return NewConverter


make_struct_based_converter('DoubleConverter', Real, 'double', '<d', 8)
make_struct_based_converter('FloatConverter', Real, 'float', '<f', 4)
make_struct_based_converter('Uint32Converter', Integral, 'uint32', '<I', 4)
make_struct_based_converter('Int32Converter', Integral, 'int32', '<i', 4)
make_struct_based_converter('Uint64Converter', Integral, 'uint64', '<Q', 8)
make_struct_based_converter('Int64Converter', Integral, 'int64', '<q', 8)
make_struct_based_converter('BoolConverter', bool, 'bool', '?', 1)


# Registered at end of file
class BytesConverter(Converter):
    """
    Handles byte arrays.

    .. codeauthor:: jmoringe
    """

    def __init__(self, wire_schema="bytes", data_type=bytes):
        super(BytesConverter, self).__init__(bytes, data_type, wire_schema)

    def serialize(self, inp):
        return inp, self.wire_schema

    def deserialize(self, inp, wire_schema):
        assert(wire_schema == self.wire_schema)
        return inp


class StringConverter(Converter):
    """
    A converter that serializes strings to bytes with a specified
    encoding

    .. codeauthor:: jwienke
    """

    def __init__(self,
                 wire_schema='utf-8-string',
                 encoding='utf-8'):
        super(StringConverter, self).__init__(bytes, str, wire_schema)
        self.__encoding = encoding

    def serialize(self, inp):
        return bytes(inp.encode(self.__encoding)), self.wire_schema

    def deserialize(self, inp, wire_schema):
        return inp.decode(self.__encoding)


class ByteArrayConverter(Converter):
    """
    A converter which just passes through the original byte array of a message.

    .. codeauthor:: jwienke
    """

    def __init__(self):
        super(ByteArrayConverter, self).__init__(bytes, bytes, '.*')

    def serialize(self, data):
        return bytes(data), self.wire_schema

    def deserialize(self, data, wire_schema):
        return bytes(data)


class SchemaAndByteArrayConverter(Converter):
    """
    A converter which passes through the wire_schema as well as the original
    byte array of a message.

    .. codeauthor:: nkoester
    """

    def __init__(self):
        super(SchemaAndByteArrayConverter, self).__init__(
            bytes, tuple, '.*')

    def serialize(self, data):
        return data[1], data[0]

    def deserialize(self, data, wire_schema):
        return wire_schema, data


class ProtocolBufferConverter(Converter):
    """
    This converter serializes and deserializes objects of protocol
    buffer data-holder classes.

    These data-holder classes are generated by the protocol buffer
    compiler protoc.

    .. codeauthor:: jmoringe
    """

    def __init__(self, message_class):
        super(ProtocolBufferConverter, self).__init__(
            bytes, message_class, '.%s' % message_class.DESCRIPTOR.full_name)

        self.__message_class = message_class

    def get_message_class(self):
        return self.__message_class

    message_class = property(get_message_class)

    def get_message_class_name(self):
        return self.message_class.DESCRIPTOR.full_name

    def serialize(self, inp):
        return bytes(inp.SerializeToString()), self.wire_schema

    def deserialize(self, inp, wire_schema):
        assert wire_schema == self.wire_schema

        output = self.message_class()
        # we need to convert back to string because bytes do not work with
        # protobuf
        output.ParseFromString(inp)
        return output

    def __str__(self):
        return '<%s for %s at 0x%x>' \
            % (type(self).__name__, self.get_message_class_name(), id(self))

    def __repr__(self):
        return str(self)


class ScopeConverter(Converter):
    """
    (De)serializes :obj:`Scope` objects.

    .. codeauthor:: jmoringe
    """

    def __init__(self):
        super(ScopeConverter, self).__init__(bytes, Scope, 'scope')

    def serialize(self, inp):
        return bytes(inp.to_bytes()), \
            self.wire_schema

    def deserialize(self, inp, wire_schema):
        assert wire_schema == self.wire_schema

        return Scope(inp.decode('ascii'))


class EventsByScopeMapConverter(Converter):
    """
    A converter for aggregated events ordered by their scope and time for each
    scope. As a client data type dictionaries are used. Think about this when
    you register the converter and also have other dictionaries to transmit.

    .. codeauthor:: jwienke
    """

    def __init__(self, converter_repository=get_global_converter_map(bytes)):
        self.__converter_repository = converter_repository
        self.__converter = ProtocolBufferConverter(EventsByScopeMap)
        super(EventsByScopeMapConverter, self).__init__(
            bytes, dict, self.__converter.wire_schema)

    def serialize(self, data):

        event_map = EventsByScopeMap()

        for scope, events in data.items():

            scope_set = event_map.sets.add()
            scope_set.scope = scope.to_bytes()

            for event in events:

                wire, wire_schema = \
                    self.__converter_repository.get_converter_for_data_type(
                        type(event.data)).serialize(event.data)

                notification = scope_set.notifications.add()
                event_to_notification(notification, event,
                                      wire_schema, wire, True)

        return self.__converter.serialize(event_map)

    def deserialize(self, wire, wire_schema):
        preliminary_map = self.__converter.deserialize(wire, wire_schema)

        output = {}

        for scope_set in preliminary_map.sets:
            scope = Scope(scope_set.scope.decode('ASCII'))
            output[scope] = []
            for notification in scope_set.notifications:

                converter = \
                    self.__converter_repository.get_converter_for_wire_schema(
                        notification.wire_schema.decode('ASCII'))
                event = notification_to_event(
                    notification, notification.data,
                    notification.wire_schema.decode('ASCII'), converter)

                output[scope].append(event)

        return output


# FIXME We do not register all available converters here to avoid
# ambiguities.
register_global_converter(NoneConverter())
register_global_converter(DoubleConverter())
# register_global_converter(FloatConverter())
# register_global_converter(Uint32Converter())
# register_global_converter(Int32Converter())
# register_global_converter(Uint64Converter())
register_global_converter(Int64Converter())
register_global_converter(BoolConverter())
register_global_converter(BytesConverter())
register_global_converter(StringConverter())
register_global_converter(ByteArrayConverter())
register_global_converter(ScopeConverter())
