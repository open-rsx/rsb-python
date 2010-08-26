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

class Enum(object):
    """
    Generates enum-like classes in python with proper printing support.
    
    @author: jwienke
    """
    
    class EnumValue(object):
        
        def __init__(self, name):
            self.__name = name
            
        def __str__(self):
            return "%s" % (self.__name)
        
        def __eq__(self, other):
            try:
                return other.__name == self.__name
            except (AttributeError, TypeError):
                return False
    
    def __init__(self, name, keys):
        """
        Generates a new enum.
        
        @param name: name of the enum to create. Will normally be the name of 
                     the variable this constructor call is assigned to. For
                     Used for printing.
        @param keys: list of enum keys to generate
        """
        
        self.__name = name
        self.__keys = keys
        self.__keyString = ""
        for key in keys:
            setattr(self, key, Enum.EnumValue(key))
            self.__keyString = self.__keyString + key + ", "
        self.__keyString = self.__keyString[:-2]

    def __str__(self):
        return "Enum %s: %s" % (self.__name, self.__keyString)
