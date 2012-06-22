
Dependencies
------------

- Python Spread module: http://www.spread.org/files/SpreadModule-1.5spread4.tgz
  You probably have to adjust the SPREAD_DIR variable in setup.py to point to
  your spread installation (line 64)
- epydoc for API documentation
- coverage for code coverage report
- unittest-xml-reporting for xml unit test reports

Installation
------------

Modify the contents of setup.cfg according to your needs. Especially the
"protocolroot" needs to be adjusted to point to your installation of
RSBProtocol. The given path must point to the folder containing the first proto
files.
Afterwards type::

  python setup.py build
  python setup.py install --prefix=$prefix

Running Unit Tests
------------------

Execute::

  python setup.py test

Reports will be generated in test-reports and on the command line.

Generating the API Documentation
--------------------------------

Execute::

  python setup.py doc

Will be available at doc/html.

Generating the Coverage Report
------------------------------

Execute::

  python setup.py coverage

Will be available in covhtml.
