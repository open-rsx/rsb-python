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

# With all the setuptools commands this does not make sense. They define
# attributes in non-init methods
# pylint: disable=attribute-defined-outside-init

from setuptools import setup
from setuptools import find_packages
from setuptools import Command
from setuptools.command.bdist_egg import bdist_egg

from distutils.command.build import build
from distutils.command.sdist import sdist
from distutils.spawn import find_executable

import os
import re
import subprocess
import shutil


def findRsbPackages(ignoreProtocol=False):
    excludes = ['test', 'examples', 'build']
    if ignoreProtocol:
        excludes.append('rsb/protocol')
    packages = find_packages(exclude=excludes)
    print('Relevant rsb packages: {}'.format(packages))
    return packages


class FetchProtocol(Command):
    '''
    A command which fetches the protocol files into this project

    .. codeauthor:: jwienke
    '''

    user_options = [('protocolroot=', 'p',
                     'root path of the protocol')]
    description = 'Fetches the protocol files into this project'

    def initialize_options(self):
        self.protocolroot = None

    def finalize_options(self):
        if self.protocolroot is None:
            raise RuntimeError('No protocolroot specified. '
                               'Use the config file or command line option.')

    def run(self):

        # if it does not exist, create the target directory for the
        # copied files
        fetchedProtocolDir = 'rsb/protocol'
        try:
            # in cases of source distributions this would kill also the fetched
            # proto files. However, for a source distribution we will never
            # reach this method because the protocolroot option will not be set
            shutil.rmtree(fetchedProtocolDir)
        except os.error:
            pass

        protoRoot = self.protocolroot
        print('Using protocol folder: {}'.format(protoRoot))
        shutil.copytree(os.path.join(protoRoot, 'rsb/protocol'),
                        fetchedProtocolDir)


class BuildProtocol(Command):
    '''
    Distutils command to build the protocol buffers.

    .. codeauthor:: jwienke
    '''

    user_options = [('protocolroot=', 'p',
                     'root path of the protocol'),
                    ('protoc=', 'c',
                     'the protoc compiler to use')]
    description = 'Generates the protocol python files from the proto files'

    def initialize_options(self):
        self.protoc = None

    def finalize_options(self):
        if self.protoc is None:
            self.protoc = find_executable('protoc')
        if self.protoc is None:
            raise RuntimeError('No protoc compiler specified or found. '
                               'Use the config file or command line option.')

    def run(self):

        try:
            self.run_command('proto')
        except RuntimeError, e:
            # for sdist fetching the protocol may fail as long as we have
            # the protocol available. Otherwise this is a real error
            self.warn('Fetching the protocol failed, but this acceptable '
                      'in cases where the files have been cached: {}'.format(
                          e))
            if not os.path.exists('rsb/protocol/Notification.proto'):
                raise e

        # create output directory
        outdir = '.'
        try:
            os.makedirs(outdir)
        except os.error:
            pass

        protoFiles = []
        for root, _, files in os.walk('rsb/protocol'):
            # collect proto files to build
            for protoFile in files:
                if protoFile[-6:] == '.proto':
                    protoFiles.append(os.path.join(root, protoFile))
            # create __init__.py files for all resulting packages
            with open(os.path.join(root, '__init__.py'), 'w'):
                pass

        print('Building protocol files: {}'.format(protoFiles))
        for proto in protoFiles:
            # TODO use project root for out path as defined in the test command
            call = [self.protoc, '-I=.', '--python_out=' + outdir, proto]
            ret = subprocess.call(call)
            if ret != 0:
                raise RuntimeError('Unable to build proto file: {}'.format(
                    proto))

        # reinitialize the list of packages as we have added new python modules
        self.distribution.packages = findRsbPackages()
        # also ensure that the build command for python module really gets
        # informed about this
        self.reinitialize_command('build_py')


class BDist_egg(bdist_egg):
    '''
    Simple wrapper around the normal bdist_egg command to require
    protobuf build before normal build.

    .. codeauthor:: jwienke

    '''

    def run(self):
        self.run_command('build_proto')
        bdist_egg.run(self)


class Build(build):
    '''
    Simple wrapper around the normal build command to require protobuf build
    before normal build.

    .. codeauthor:: jwienke
    '''

    def run(self):
        self.run_command('build_proto')
        build.run(self)


class Sdist(sdist):
    '''
    Simple wrapper around the normal sdist command to require protobuf build
    before generating the source distribution..

    .. codeauthor:: jwienke
    '''

    def run(self):
        # fetch the protocol before building the source distribution so that
        # we have a cached version and each user can rebuild the protocol
        # with his own protobuf version
        self.run_command('proto')

        # reinitialize the list of packages for the distribution to
        # include the precompiled protocol results from protoc which
        # might conflict with the user's version
        self.distribution.packages = findRsbPackages(ignoreProtocol=True)

        sdist.run(self)


def get_git_commit():
    try:
        return subprocess.check_output(
            ['git', 'log', '-1', '--pretty=format:g%h'])
    except subprocess.CalledProcessError:
        return 'archive'


def determineProtocVersion():
    '''
    Determines the protoc version available to compile the protocol to python
    files. This is required to define the protobuf library dependency version.
    '''
    protoc = find_executable('protoc')
    print('Using protoc executable from {} '
          'to determine the protobuf library version to use. '
          'Adjust PATH if something different is desired.'.format(protoc))
    proc = subprocess.Popen([protoc, '--version'], stdout=subprocess.PIPE)
    (versionOutput, _) = proc.communicate()
    protocVersionParts = versionOutput.split(' ')
    if len(protocVersionParts) != 2:
        raise RuntimeError(
            "Unexpected version out from protoc: '{}'".format(versionOutput))
    # Only use the first two version components as the patch part seems to be
    # unrelated to breaking changes.
    # See: https://github.com/google/protobuf/issues/3602
    return [int(x) for x in protocVersionParts[1].split('.')[:2]]


def generateVersionFile(version, commit):
    '''
    Generates a version.py file from available version information to provide
    version information at runtime.
    '''
    with open(os.path.join('rsb', 'version.py.in'), 'r') as template:
        with open(os.path.join('rsb', 'version.py'), 'w') as target:
            target.write(
                template.read().replace(
                    '@VERSION@', version).replace(
                        '@COMMIT@', commit))


version = '1.0.0-dev'
commit = get_git_commit()
print('This is version {version}-{commit}'.format(version=version,
                                                  commit=commit))
generateVersionFile(version, commit)

protocVersion = determineProtocVersion()
print('Determined protobuf version to be {version}'.format(
    version=protocVersion))

setup(name='rsb-python',
      version=version,
      description="Fully event-driven Robotics Service Bus",
      author='Johannes Wienke',
      author_email='jwienke@techfak.uni-bielefeld.de',
      license='LGPLv3+',
      url='https://code.cor-lab.org/projects/rsb',
      keywords=['middleware', 'bus', 'robotics'],
      classifiers=[
        'Programming Language :: Python',
        'Development Status :: 5 - Production/Stable',
        'Environment :: Other Environment',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: '
          'GNU Library or Lesser General Public License (LGPL)',
        'Operating System :: OS Independent',
        'Topic :: Communications',
        'Topic :: Scientific/Engineering',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Python Modules',
        ],

      install_requires=['protobuf>={}.{},<{}.{}'.format(
          protocVersion[0],
          protocVersion[1],
          protocVersion[0],
          protocVersion[1] + 1)],
      setup_requires=['nose>=1.3',
                      'coverage',
                      'nose-testconfig'],

      packages=findRsbPackages(),

      cmdclass={
          'proto':       FetchProtocol,
          'build_proto': BuildProtocol,
          'sdist':       Sdist,
          'build':       Build,
          'bdist_egg':   BDist_egg,
      })
