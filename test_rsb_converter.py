# ============================================================
#
# Copyright (C) 2011-2016 Jan Moringen
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

import re
from uuid import uuid4

import pytest

from rsb import Event, EventId, Scope
import rsb.converter
from rsb.converter import (Converter,
                           ConverterMap,
                           EventsByScopeMapConverter,
                           NoneConverter,
                           PredicateConverterList,
                           ScopeConverter,
                           StringConverter,
                           UnambiguousConverterMap)


class ConflictingStringConverter(Converter):
    def __init__(self):
        super().__init__(wire_type=bytes,
                         wire_schema="utf-8-string", data_type=float)

    def serialize(self, data):
        return str()

    def deserialize(self, wire, wire_schema):
        return str(wire)


class TestConverterMap:
    def test_add_converter(self):
        converter_map = ConverterMap(str)
        converter_map.add_converter(StringConverter())
        converter_map.add_converter(ConflictingStringConverter())
        with pytest.raises(Exception):
            converter_map.add_converter(StringConverter())
        converter_map.add_converter(StringConverter(), replace_existing=True)


class TestUnambiguousConverterMap:
    def test_add_converter(self):
        converter_map = UnambiguousConverterMap(str)
        converter_map.add_converter(StringConverter())
        with pytest.raises(Exception):
            converter_map.add_converter(ConflictingStringConverter())
        with pytest.raises(Exception):
            converter_map.add_converter(ConflictingStringConverter(), True)
        converter_map.add_converter(StringConverter(), replace_existing=True)


class TestPredicateConverterList:

    def test_add_converter(self):
        converter_list = PredicateConverterList(str)
        converter_list.add_converter(StringConverter())
        converter_list.add_converter(
            StringConverter(),
            wire_schema_predicate=lambda wire_schema: True)
        converter_list.add_converter(
            StringConverter(),
            data_type_predicate=lambda data_type: True)

    def test_get_converter(self):
        v1 = StringConverter()
        v2 = StringConverter()

        always_true = PredicateConverterList(str)
        always_true.add_converter(
            v1,
            wire_schema_predicate=lambda wire_schema: True,
            data_type_predicate=lambda data_type: True)
        assert always_true.get_converter_for_wire_schema("") is v1
        assert always_true.get_converter_for_wire_schema("bla") is v1

        regex = PredicateConverterList(str)
        regex.add_converter(
            v1,
            wire_schema_predicate=lambda wire_schema:
                re.match(".*foo.*", wire_schema),
            data_type_predicate=lambda data_type:
                re.match(".*foo.*", data_type))
        with pytest.raises(KeyError):
            regex.get_converter_for_wire_schema("")
        with pytest.raises(KeyError):
            regex.get_converter_for_wire_schema("bla")
        assert regex.get_converter_for_wire_schema("foo") is v1
        assert regex.get_converter_for_wire_schema("foobar") is v1
        with pytest.raises(KeyError):
            regex.get_converter_for_data_type("")
        with pytest.raises(KeyError):
            regex.get_converter_for_data_type("bla")
        assert regex.get_converter_for_data_type("foo") is v1
        assert regex.get_converter_for_data_type("foobar") is v1

        mixed = PredicateConverterList(str)
        mixed.add_converter(
            v1,
            wire_schema_predicate=lambda wire_schema:
                re.match(".*foo.*", wire_schema),
            data_type_predicate=lambda data_type:
                re.match(".*foo.*", data_type))
        mixed.add_converter(v2,
                            wire_schema_predicate=lambda wire_schema: True,
                            data_type_predicate=lambda data_type: True)
        assert mixed.get_converter_for_wire_schema("") is v2
        assert mixed.get_converter_for_wire_schema("bla") is v2
        assert mixed.get_converter_for_wire_schema("foo") is v1
        assert mixed.get_converter_for_wire_schema("foobar") is v1
        assert mixed.get_converter_for_data_type("") is v2
        assert mixed.get_converter_for_data_type("bla") is v2
        assert mixed.get_converter_for_data_type("foo") is v1
        assert mixed.get_converter_for_data_type("foobar") is v1


class TestNoneConverter:
    def test_roundtrip(self):
        converter = NoneConverter()
        assert converter.deserialize(*converter.serialize(None)) is None


class TestStringConverter:

    @pytest.mark.parametrize('data', [
        'asd' + chr(270) + chr(40928),
        'i am a normal string',
    ])
    def test_roundtrip_utf8(self, data):
        converter = StringConverter()
        assert converter.deserialize(*converter.serialize(data)) == data

    def test_roundtrip_ascii(self):
        converter = StringConverter(wire_schema="ascii-string",
                                    encoding="ascii")
        orig = "foooo"
        assert converter.deserialize(*converter.serialize(orig)) == orig

    def test_charset_errors(self):
        ascii_converter = StringConverter(wire_schema="ascii-string",
                                          encoding="ascii")
        with pytest.raises(UnicodeEncodeError):
            ascii_converter.serialize("test" + chr(266))
        with pytest.raises(UnicodeDecodeError):
            ascii_converter.deserialize(
                bytes(list(range(133))), 'ascii-string')


class TestScopeConverter:

    def test_round_trip(self):
        converter = ScopeConverter()

        root = Scope('/foo/bar')
        assert converter.deserialize(*converter.serialize(root)) == root

        some_scope = Scope('/foo/bar')
        assert converter.deserialize(
            *converter.serialize(some_scope)) == some_scope


class TestEventsByScopeMapConverter:

    def test_empty_roundtrip(self):

        data = {}
        converter = EventsByScopeMapConverter()
        assert converter.deserialize(*converter.serialize(data)) == data

    def test_roundtrip(self):
        self.max_diff = None

        data = {}
        scope1 = Scope("/a/test")
        event1 = Event(event_id=EventId(uuid4(), 32), scope=scope1,
                       method="foo", data=42, data_type=int,
                       user_times={"foo": 1231234.0})
        event1.meta_data.set_send_time()
        event1.meta_data.set_receive_time()
        event2 = Event(event_id=EventId(uuid4(), 1001), scope=scope1,
                       method="fooasdas", data=422, data_type=int,
                       user_times={"bar": 1234.05})
        event2.meta_data.set_send_time()
        event2.meta_data.set_receive_time()
        data[scope1] = [event1, event2]

        converter = EventsByScopeMapConverter()
        roundtripped = converter.deserialize(*converter.serialize(data))

        assert len(roundtripped) == 1
        assert scope1 in roundtripped
        assert len(data[scope1]) == len(roundtripped[scope1])

        for orig, converted in zip(data[scope1], roundtripped[scope1]):

            assert orig.event_id == converted.event_id
            assert orig.scope == converted.scope
            # This test currently does not work correctly without a patch for
            # the converter selection for fundamental types
            # self.assertEqual(orig.data_type, converted.data_type)
            assert orig.data == converted.data
            assert pytest.approx(orig.meta_data.create_time) == \
                converted.meta_data.create_time
            assert pytest.approx(orig.causes) == converted.causes


@pytest.mark.parametrize('converter,values', [
    (rsb.converter.DoubleConverter(), [0.0, -1.0, 1.0]),
    (rsb.converter.FloatConverter(), [0.0, -1.0, 1.0]),
    (rsb.converter.Int32Converter(), [0, -1, 1, -24378, ((1 << 31) - 1)]),
    (rsb.converter.Int64Converter(), [0, -1, 1, -24378, ((1 << 63) - 1)]),
    (rsb.converter.Uint32Converter(), [0, 1, 24378, ((1 << 32) - 1)]),
    (rsb.converter.Uint64Converter(), [0, 1, 24378, ((1 << 32) - 1)]),
    (rsb.converter.BoolConverter(), [True, False]),
])
def test_structure_base_converters(converter, values):
    for value in values:
        assert value == converter.deserialize(*converter.serialize(value))
