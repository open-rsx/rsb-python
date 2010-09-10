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

from distutils.core import setup
from distutils.extension import Extension
from distutils.core import Command
from distutils import ccompiler
from unittest import TextTestRunner, TestLoader
from distutils.command import build
import os
import glob
import sys
import subprocess
import commands

# include dirs needed
from ConfigParser import SafeConfigParser

class ApiDocCommand(Command):
    '''
    Distutils command used to build the api documentation with epydoc.
    
    @author: jwienke
    @todo: re-enable this class
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
        buildCmd = self.get_finalized_command('build')
        buildCmd.run()
        
        # build directory that was used for the command before
        buildDir = os.path.join(os.getcwd(), buildCmd.build_lib)
        
        # build the argument string
        cmdline = ["epydoc"]
        cmdline.append("--" + self.format)
        cmdline.append("-o")
        cmdline.append(os.path.join("doc", self.format))
        if self.verbose:
            cmdline.append("-v")
        cmdline.append("--config")
        cmdline.append("epydoc.config")
        
        # call epydoc according to the selected configuration
        env = os.environ
        ppath = ""
        for p in sys.path:
            ppath += p + os.path.pathsep
        ppath += buildDir
        env['PYTHONPATH'] = ppath
        subprocess.call(cmdline, env=env)

class TestCommand(Command):
    '''
    Distutils command running the unit tests found in the directory 'test'.
    
    @author: jwienke
    '''
    
    user_options = []
    description = "runs the unit tests"

    def initialize_options(self):
        self.__projectRoot = ""
        if ("/" in __file__):
            self.__projectRoot = str(__file__).rpartition("/")[0]
    
    def finalize_options(self):
        pass

    def run(self):
        self.__runTests()
        
    def __runTests(self):
        '''
        Runs all unit tests found in the folder 'test'.
        '''
        
        # append test path to pythonpath
        sys.path.append(os.path.join(self.__projectRoot, "src"))
        sys.path.append(os.path.join(self.__projectRoot, "test"))
        sys.path.append(os.path.join(self.__projectRoot, "build"))
        
        testFiles = self.__findTestModules()
        #print("trying to load test cases: %s" % testFiles)

        tests = TestLoader().loadTestsFromNames(testFiles)
        
        t = TextTestRunner(verbosity = 5)
        t.run(tests)

    def __findTestModules(self):
        '''
        Returns a list of test files found in the test directory.
        '''
        
        testFiles = []
        for root, dirs, files in os.walk(os.path.join(self.__projectRoot, 'test')):
            for file in files:
                if file[-3:] == ".py" and not file == "__init__.py":
                    testFiles.append(file[:-3])
                
        return testFiles
    
class BuildProtobufs(Command):
    '''
    Distutils command to build the protocol buffers.
    
    @author: jwienke
    '''
    
    user_options = []
    description = "runs the unit tests"

    def initialize_options(self):
        pass
    
    def finalize_options(self):
        pass

    def run(self):
        
        protoRoot = "/vol/nao/releases/cuttingedge/share/rsbprotocol"
        protoFiles = []
        for root, dirs, files in os.walk(protoRoot):
            for file in files:
                if file[-6:] == ".proto":
                    protoFiles.append(os.path.join(root, file))
        
        for proto in protoFiles:
            # TODO use project root for out path as defined in the test command
            call = ["protoc", "-I=" + protoRoot, "--python_out=build", proto]
            #print("calling: %s" % call)
            ret = subprocess.call(call)
            if ret != 0:
                raise RuntimeError("Unable to build proto file: %s" % proto)
  

setup (name = 'RSB - Robotic Service Bus', 
       version = '0.1', 
       description = ''''
                     TODO!!!
                     ''', 
       author = 'Johannes Wienke',
       author_email = 'jwienke@techfak.uni-bielefeld.de',
       packages = ['rsb', 'rsb.transport'],
       package_dir = {'rsb': 'src/rsb',
                      'rsb.transport' : 'src/rsb/transport'},
       ext_modules = ["dummy"],
       cmdclass = {'build_ext': BuildProtobufs,
                   'test': TestCommand}) #'doc': ApiDocCommand
