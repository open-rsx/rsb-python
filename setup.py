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

from setuptools import setup
from setuptools import find_packages
from setuptools import Command
from setuptools.command.bdist_egg import bdist_egg

from distutils.command.build import build
from distutils.command.sdist import sdist
from distutils.spawn import find_executable

from unittest import TestResult

import os
import re
import setuptools.command.test
import subprocess
import sys
import time
import shutil
import contextlib

def findRsbPackages(ignoreProtocol=False):
    excludes = ["test", "examples", "build"]
    if ignoreProtocol:
        excludes.append("rsb/protocol")
    packages = find_packages(exclude=excludes)
    print("Relevant rsb packages: %s" % packages)
    return packages

@contextlib.contextmanager
def nullContext():
    yield

class CommandStarter(object):
    """
    Starts a command and end it again using the python context manager protocol.

    @author: jwienke
    """

    def __init__(self, command):
        self.__command = command

    def __enter__(self):
        self.__open = subprocess.Popen(self.__command)
        time.sleep(5)

    def __exit__(self, exc_type, exc_value, traceback):
        self.__open.terminate()
        self.__open.wait()

class FetchProtocol(Command):
    '''
    A command which fetches the protocol files into this project

    @author: jwienke
    '''

    user_options = [('protocolroot=', 'p',
                     "root path of the protocol")]
    description = "Fetches the protocol files into this project"

    def initialize_options(self):
        self.protocolroot = None

    def finalize_options(self):
        if self.protocolroot == None:
            raise RuntimeError("No protocolroot specified. Use the config file or command line option.")

    def run(self):

        # if it does not exist, create the target directory for the copied files
        fetchedProtocolDir = "rsb/protocol"
        try:
            # in cases of source distributions this would kill also the fetched
            # proto files. However, for a source distribution we will never
            # reach this method because the protocolroot option will not be set
            shutil.rmtree(fetchedProtocolDir)
        except os.error:
            pass

        protoRoot = self.protocolroot
        print("Using protocol folder: %s" % protoRoot)
        shutil.copytree(os.path.join(protoRoot, "rsb/protocol"), fetchedProtocolDir)

class BuildProtocol(Command):
    '''
    Distutils command to build the protocol buffers.

    @author: jwienke
    '''

    user_options = [('protocolroot=', 'p',
                     "root path of the protocol"),
                    ('protoc=', 'c',
                     "the protoc compiler to use")]
    description = "Generates the protocol buffers from the previously protocol definition"

    def initialize_options(self):
        self.protoc = None

    def finalize_options(self):
        if self.protoc == None:
            self.protoc = find_executable("protoc")
        if self.protoc == None:
            raise RuntimeError("No protoc compiler specified or found. Use the config file or command line option.")

    def run(self):

        try:
            self.run_command('proto')
        except RuntimeError, e:
            # for sdist fetching the protocol may fail as long as we have
            # the protocol available. Otherwise this is a real error
            self.warn("Fetching the protocol failed, but this acceptable in cases where the files have been cached: %s" % e)
            if not os.path.exists("rsb/protocol/Notification.proto"):
                raise e

        # create output directory
        outdir = "."
        try:
            os.makedirs(outdir)
        except os.error:
            pass

        protoFiles = []
        for root, dirs, files in os.walk("rsb/protocol"):
            # collect proto files to build
            for file in files:
                if file[-6:] == ".proto":
                    protoFiles.append(os.path.join(root, file))
            # create __init__.py files for all resulting packages
            with open(os.path.join(root, '__init__.py'), 'w'):
                pass

        print("Building protocol files: %s" % protoFiles)
        for proto in protoFiles:
            # TODO use project root for out path as defined in the test command
            call = [self.protoc, "-I=.", "--python_out=" + outdir, proto]
            #print("calling: %s" % call)
            ret = subprocess.call(call)
            if ret != 0:
                raise RuntimeError("Unable to build proto file: %s" % proto)

        # reinitialize the list of packages as we have added new python modules
        self.distribution.packages = findRsbPackages()
        # also ensure that the build command for python module really gets informed about this
        self.reinitialize_command("build_py")

class Coverage(Command):
    """
    A command to generate a coverage report using coverage.py.

    @author: jwienke
    """

    user_options = [('spread=', 'd',
                     "spread executable to use")]
    description = "generates a coverage report"

    def initialize_options(self):
        self.spread = None

    def finalize_options(self):
        import rsb
        if self.spread == None and rsb.haveSpread():
            self.spread = find_executable("spread")
            if self.spread == None:
                print("WARNING: no spread daemon found. Make sure that one is running before starting the coverage report")

    def run(self):

        spread = nullContext()
        if self.spread:
            spread = CommandStarter([self.spread, "-n", "localhost", "-c", "test/spread.conf"])

        with spread:

            import coverage
            cov = coverage.coverage(branch=True, source=["rsb"], omit=["*_pb2*"])
            cov.erase()
            cov.start()
            import test
            suite = test.suite()
            results = TestResult()
            suite.run(results)
            if not results.wasSuccessful():
                print("Unit tests failed while generating test report.")
            cov.stop()
            cov.html_report(directory='covhtml')
            cov.xml_report(outfile='coverage.xml')

class BDist_egg(bdist_egg):
    """
    Simple wrapper around the normal bdist_egg command to require protobuf build
    before normal build.

    @author: jwienke
    """

    def run(self):
        self.run_command('build_proto')
        bdist_egg.run(self)

class Build(build):
    """
    Simple wrapper around the normal build command to require protobuf build
    before normal build.

    @author: jwienke
    """

    def run(self):
        self.run_command('build_proto')
        build.run(self)

class Sdist(sdist):
    """
    Simple wrapper around the normal sdist command to require protobuf build
    before generating the source distribution..

    @author: jwienke
    """

    def run(self):
        # fetch the protocol before building the source distribution so that
        # we have a cached version and each user can rebuild the protocol
        # with his own protobuf version
        self.run_command('proto')

        # reinitialize the list of packages for the distribution to include the
        # precompiled protocol results from protoc which might conflict with the
        # user's version
        self.distribution.packages = findRsbPackages(ignoreProtocol=True)

        sdist.run(self)

class Test(setuptools.command.test.test):
    """
    Wrapper for test command to execute build before testing use a custom test
    runner. It also starts a spread daemon.

    @author: jwienke
    """

    user_options = setuptools.command.test.test.user_options \
        + [ ('spread=',     'd',  "Spread executable to use"),
            ('spreadport=', 'p',  "Port the spread daemon should use"),
            ('socketport=', None, 'Port which should be used by socket transport') ]

    def initialize_options(self):
        setuptools.command.test.test.initialize_options(self)
        self.spread = None
        self.spreadport = 4803
        self.socketport = 55555

    def finalize_options(self):

        import rsb

        setuptools.command.test.test.finalize_options(self)
        if self.spread == None and rsb.haveSpread():
            self.spread = find_executable("spread")
            if self.spread == None:
                print("WARNING: no spread daemon found. Make sure that one is running before starting the unit tests")

    def run(self):
        self.run_command('build')

        for name, socketenabled, spreadenabled in [ ('spread', '0', '1'),
                                                    ('socket', '1', '0') ]:
            with open('test/with-%s.conf' % name, 'w') as f:
                f.write("""[introspection]
enabled = 0

[transport.spread]
enabled = {spreadenabled}
port    = {spreadport}

[transport.socket]
enabled = {socketenabled}
port    = {socketport}"""
                        .format(spreadenabled = spreadenabled,
                                spreadport    = self.spreadport,
                                socketenabled = socketenabled,
                                socketport    = self.socketport))

        with open('test/spread.conf', 'w') as f:
            f.write("""Spread_Segment 127.0.0.255:{spreadport} {{
localhost 127.0.0.1
}}
SocketPortReuse = ON
                    """
                    .format(spreadport = self.spreadport))

        # if required, start a spread daemon
        spread = nullContext()
        if self.spread and not self.spread == 'use-running':
            spread = CommandStarter([self.spread, "-n", "localhost", "-c", "test/spread.conf"])
        with spread:
            setuptools.command.test.test.run(self)

    def run_tests(self):
        """
        This method is overridden because setuptools 0.6 does not contain
        support for handling different test runners. In later versions it is
        probably not required to override this method.
        """
        import unittest
        import xmlrunner
        from pkg_resources import EntryPoint
        loader_ep = EntryPoint.parse("x=" + self.test_loader)
        loader_class = loader_ep.load(require=False)
        unittest.main(
            None, None, [unittest.__file__] + self.test_args,
            testLoader=loader_class(),
            testRunner=xmlrunner.XMLTestRunner(output='test-reports')
        )

def defineProjectVersion(majorMinor):

    # first, try to get the required information from git directly and put them
    # in cache files, which can also be created manually in cases we export an
    # archive

    def checkedProgramOutput(commandLine, filename):
        '''
        Tries to get the stdout of a program and writes it to the specified file
        in cases where the execution of the program succeeded. Otherwise the
        file remains untouched.
        '''

        try:
            proc = subprocess.Popen(commandLine, stdout=subprocess.PIPE)
            (versionOutput, _) = proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError("Git process terminated with return code %s" % proc.returncode)
            if len(versionOutput.strip()) == 0:
                raise RuntimeError("Git process did not produce output")

            with open(filename, 'w') as f:
                f.write(versionOutput)
        except:
            print("Error calling git. Add git to the PATH.")

    checkedProgramOutput(['git', 'describe', '--tags', '--match', 'release-*.*', '--long'], 'gitversion')
    checkedProgramOutput(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], 'gitbranch')

    # grab the relevant information from the files
    patchVersion = '0'
    lastCommit = 'archive'

    try:
        gitversion = open('gitversion', 'r').read().strip()
        versionMatch = re.match('^(.+)-([0-9]+)-(g[0-9a-fA-F]+)$', gitversion.strip())
        groups = versionMatch.groups()
        if len(groups) == 3:
            patchVersion = groups[1]
            lastCommit = groups[2]
        else:
            print("Unable to extract patch version and last commit from version string '%s'" % gitversion.strip())
    except Exception, e:
        print("Unable to read from the gitversion file: %s" % e)

    gitbranch = None
    try:
        gitbranch = open('gitbranch', 'r').read().strip()
    except:
        print("Unable to read from the gitbranch file")
    if gitbranch is not None and re.match('[0-9]+\.[0-9]+', gitbranch.strip()) is not None:
        print("This is a release branch. Defining ")
    else:
        patchVersion = '0'
        print("Not on a release branch. Skipping patch version")

    # if we were still not successful defining the commit hash, try to get it
    # using git log
    if lastCommit == 'archive':
        p = subprocess.Popen(['git', 'log' ,'-1', '--pretty=format:g%h'], stdout=subprocess.PIPE)
        lastCommitOnline, _ = p.communicate()
        if p.returncode == 0:
            lastCommit = str(lastCommitOnline).strip()

    return ("%s.%s" % (majorMinor, patchVersion), str(lastCommit))

(version, commit) = defineProjectVersion('0.12')

print("This is version %s-%s" % (version, commit))

# generate a version file so that version information is available at runtime
with open(os.path.join('rsb', 'version.py.in'), 'r') as template:
    with open(os.path.join('rsb', 'version.py'), 'w') as target:
        target.write(template.read().replace('@VERSION@', version).replace('@COMMIT@', commit))

# determine the protoc version we are working with
protoc = find_executable("protoc")
print('Using protoc executable from %s to determine the protobuf library version to use. Adjust PATH if something different is desired.' % protoc)
proc = subprocess.Popen([protoc, '--version'], stdout=subprocess.PIPE)
(versionOutput, _) = proc.communicate()
protocVersionParts = versionOutput.split(' ')
if len(protocVersionParts) != 2:
    raise RuntimeError("Unexpected version out from protoc: '%s'" % versionOutput)
protocVersion = protocVersionParts[1]
print("I will request a protobuf library of version %s" % protocVersion)

setup(name='rsb-python',
      version = version,
      description='''
                  Fully event-driven Robotics Service Bus
                  ''',
      author='Johannes Wienke',
      author_email='jwienke@techfak.uni-bielefeld.de',
      license="LGPLv3+",
      url="https://code.cor-lab.org/projects/rsb",
      keywords=["middleware", "bus", "robotics"],
      classifiers=[
        "Programming Language :: Python",
        "Development Status :: 5 - Production/Stable",
        "Environment :: Other Environment",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)",
        "Operating System :: OS Independent",
        "Topic :: Communications",
        "Topic :: Scientific/Engineering",
        "Topic :: Software Development :: Libraries",
        "Topic :: Software Development :: Libraries :: Python Modules",
        ],

      install_requires=["protobuf==%s" % protocVersion],
      setup_requires=["coverage", "setuptools-epydoc", "unittest-xml-reporting", "setuptools-lint"],

      extras_require={
        'spread-transport':  ["SpreadModule>=1.5spread4"],
      },

      dependency_links=['http://www.spread.org/files/SpreadModule-1.5spread4.tgz#egg=SpreadModule-1.5spread4'],

      packages=findRsbPackages(),
      test_suite="test.suite",

      cmdclass={
          'proto':       FetchProtocol,
          'build_proto': BuildProtocol,
          'sdist' :      Sdist,
          'build' :      Build,
          'bdist_egg':   BDist_egg,
          'test' :       Test,
          'coverage' :   Coverage
      }
  )
