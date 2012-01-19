# ============================================================
#
# Copyright (C) 2010 by Johannes Wienke <jwienke at techfak dot uni-bielefeld dot de>
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
import localtransporttest

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
    suite.addTest(localtransporttest.suite())
    return suite
