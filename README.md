# Introduction #

This repository contains the Python implementation of the [Robotics Service Bus](https://github.com/open-rsx) middleware.

**The full documentation for RSB can be found at <https://docs.cor-lab.de/manual/rsb-trunk/index.html>.**

- epydoc for API documentation
- coverage for code coverage report
- unittest-xml-reporting for xml unit test reports

# Building and Installing

## Installation ##

Modify the contents of `setup.cfg` according to your needs. Especially the
"protocolroot" needs to be adjusted to point to your installation of
RSBProtocol. The given path must point to the folder containing the first proto
files.
Afterwards type:

```shell
python setup.py build
python setup.py install --prefix=$prefix
```

## Running Unit Tests ##

Execute:

```shell
python setup.py test
```

Reports will be generated in test-reports and on the command line.

## Generating the API Documentation ##

Execute:

```shell
python setup.py doc
```

Will be available at `doc/html`.

## Generating the Coverage Report ##

Execute::

```shell
python setup.py coverage
```

Will be available in `covhtml`.

# Contributing #

If you want to contribute to this project, please

- Submit your intended changes as coherent pull requests
- Rebase onto the master branch and squash any fixups and corrections
- Make sure the unit tests pass (See [Running Unit Tests](#running-unit-tests))

# Acknowledgments #

The development of this software has been supported as follows:

- This research was funded by the EC 7th Framework Programme (FP7/2007-2013), in the TA2 (grant agreement ICT-2007-214 793) and HUMAVIPS (grant aggrement ICT-2009-247525) projects.
- The development of this software was supported by CoR-Lab, Research Institute for Cognition and Robotics Bielefeld University.
- This work was supported by the Cluster of Excellence Cognitive Interaction Technology ‘CITEC’ (EXC 277) at Bielefeld University, which is funded by the German Research Foundation (DFG).
