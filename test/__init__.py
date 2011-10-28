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

import unittest

import rsb

import coretest
import eventprocessingtest
import filtertest
import rsbspreadtest
import transporttest
import convertertest
import utiltest
import patternstest

logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)

class ConfigSettingTestSuite (unittest.TestSuite):
    def run(self, *args):
        rsb.getDefaultParticipantConfig()
        rsb.setDefaultParticipantConfig(rsb.ParticipantConfig.fromFile('test/with-spread.conf'))

        super(ConfigSettingTestSuite, self).run(*args)

def suite():
    suite = ConfigSettingTestSuite()
    suite.addTest(coretest.suite())
    suite.addTest(eventprocessingtest.suite())
    suite.addTest(filtertest.suite())
    suite.addTest(rsbspreadtest.suite())
    suite.addTest(transporttest.suite())
    suite.addTest(convertertest.suite())
    suite.addTest(utiltest.suite())
    suite.addTest(patternstest.suite())
    return suite
