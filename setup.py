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

from setuptools import setup
from setuptools import find_packages
from setuptools import Command

from distutils.command.build import build
from distutils.spawn import find_executable

from unittest import TestResult

import coverage
import os
import setuptools.command.test
import subprocess
import sys

class ApiDocCommand(Command):
    '''
    Distutils command used to build the api documentation with epydoc.
    
    @author: jwienke
    '''

    user_options = [('format=', 'f',
                     "the output format to use (html and pdf)"),
                     ("verbose", 'v', "print verbose warnings")]
    description = "generates the api documentation as html or pdf"

    FORMAT_HTML = "html"
    FORMAT_PDF = "pdf"

    def initialize_options(self):
        self.format = None
        self.verbose = False

    def finalize_options(self):
        if self.format is None:
            self.format = self.FORMAT_HTML
        if not self.format in [self.FORMAT_HTML, self.FORMAT_PDF]:
            self.format = self.FORMAT_HTML

    def run(self):

        # ensure that everything that's needed is built
        self.run_command('build')

        outdir = os.path.join("doc", self.format)
        try:
            os.makedirs(outdir)
        except OSError:
            pass

        # build the argument string
        cmdline = ["epydoc"]
        cmdline.append("--" + self.format)
        cmdline.append("-o")
        cmdline.append(outdir)
        if self.verbose:
            cmdline.append("-v")
        cmdline.append("--config")
        cmdline.append("epydoc.config")

        # call epydoc according to the selected configuration
        env = os.environ
        ppath = ""
        for p in sys.path:
            ppath += p + os.path.pathsep
        env['PYTHONPATH'] = ppath
        subprocess.call(cmdline, env=env)

class BuildProtobufs(Command):
    '''
    Distutils command to build the protocol buffers.
    
    @author: jwienke
    '''

    user_options = [('protocolroot=', 'p',
                     "root path of the protocol"),
                    ('protoc=', 'c',
                     "the protoc compiler to use")]
    description = "generates the protocol buffers from the previously installed protocol project"

    def initialize_options(self):
        self.protocolroot = None
        self.protoc = None

    def finalize_options(self):
        if self.protocolroot == None:
            raise RuntimeError("No protocolroot specified. Use the config file or command line option.")
        if self.protoc == None:
            self.protoc = find_executable("protoc")
        if self.protoc == None:
            raise RuntimeError("No protoc compiler specified or found. Use the config file or command line option.")

    def run(self):

        protoRoot = self.protocolroot
        print("Using protocol folder: %s" % protoRoot)
        protoFiles = []
        for root, dirs, files in os.walk(protoRoot):
            for file in files:
                if file[-6:] == ".proto":
                    protoFiles.append(os.path.join(root, file))

        if len(protoFiles) == 0:
            raise RuntimeError(("Could not find rsb protocol at '%s'. " +
                               "Please specify it's location using the command option or config file.") % protoRoot)

        print("Building protocol files: %s" % protoFiles)
        for proto in protoFiles:
            # TODO use project root for out path as defined in the test command
            call = [self.protoc, "-I=" + protoRoot, "--python_out=rsb/rsbspread", proto]
            #print("calling: %s" % call)
            ret = subprocess.call(call)
            if ret != 0:
                raise RuntimeError("Unable to build proto file: %s" % proto)

class Coverage(Command):
    """
    A command to generate a coverage report using coverage.py.
    
    @author: jwienke
    """

    user_options = []
    description = "generates a coverag report"

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        cov = coverage.coverage(branch=True,source=["rsb"],omit=["*_pb2*"])
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

class Build(build):
    """
    Simple wrapper around the normal build command to require protobuf build
    before normal build.
    
    @author: jwienke
    """

    def run(self):
        self.run_command('proto')
        build.run(self)

class Test(setuptools.command.test.test):
    """
    Wrapper for test command to execute build before.
    
    @author: jwienke
    """

    def run(self):
        self.run_command('build')
        setuptools.command.test.test.run(self)

setup(name='RSB - Robotic Service Bus',
      version='0.1',
      description='''
                  Fully event-driven Robotics Systems Bus
                  ''',
      author='Johannes Wienke',
      author_email='jwienke@techfak.uni-bielefeld.de',
      license="GPLv2",
      url="https://code.cor-lab.org/projects/rsb",

      packages=find_packages(exclude=["test", "examples", "build"]),
      test_suite="test.suite",

      cmdclass={'doc' : ApiDocCommand,
                'proto': BuildProtobufs,
                'build' : Build,
                'test' : Test,
                'coverage' : Coverage},
      )
