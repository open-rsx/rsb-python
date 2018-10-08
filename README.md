# Introduction #

This repository contains the Python implementation of the [Robotics Service Bus](https://github.com/open-rsx) middleware.

**The full documentation for RSB can be found at <https://docs.cor-lab.de/manual/rsb-trunk/index.html>.**

- epydoc for API documentation
- coverage for code coverage report
- unittest-xml-reporting for xml unit test reports

# Building and Installing

## Installation ##

```shell
python setup.py build
python setup.py install --prefix=$prefix
```

## Running Unit Tests ##

Preparation:

1. Install [pyenv] and configure it as described
1. With [pyenv], install Python 3.6 and 3.7 and make them active for this project
1. Install [tox]

Execute:

```shell
tox
```

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

[pyenv]: https://github.com/pyenv/pyenv
[tox]: https://tox.readthedocs.io
