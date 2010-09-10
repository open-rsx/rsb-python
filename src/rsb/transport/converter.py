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

from rsb.transport import Converter
from rsb.transport import registerGlobalConverter

# --- converters with str as serialization type ---

class StringConverter(Converter):
    """
    An adapter to serialize strings to strings. ;)
    
    @author: jwienke
    """
    
    def __init__(self):
        Converter.__init__(self, "string", str)

    def _serialize(self, input):
        return str(input)

    def deserialize(self, input):
        return str(input)
    
registerGlobalConverter(StringConverter())