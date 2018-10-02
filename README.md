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
