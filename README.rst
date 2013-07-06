=========
autoflake
=========

.. image:: https://travis-ci.org/myint/autoflake.png?branch=master
   :target: https://travis-ci.org/myint/autoflake
   :alt: Build status

.. image:: https://coveralls.io/repos/myint/autoflake/badge.png?branch=master
   :target: https://coveralls.io/r/myint/autoflake
   :alt: Test coverage status


Introduction
============

*autoflake* removes unused imports and unused variables from Python code. It
makes use of pyflakes_ to do this.

By default, autoflake only removes unused imports for modules that are part of
the standard library. (Other modules may have side effects that make them
unsafe to remove automatically.) Removal of unused variables is also disabled
by default.

autoflake also removes useless ``pass`` statements.

.. _pyflakes: http://pypi.python.org/pypi/pyflakes


Example
=======

Running autoflake on the below example::

    $ autoflake --in-place --remove-unused-variables example.py

.. code-block:: python

    import math
    import re
    import os
    import random
    import multiprocessing
    import grp, pwd, platform
    import subprocess, sys


    def foo():
        try:
            from abc import ABCMeta, WeakSet
        except ImportError as exception:
            print(sys.version)
        return math.pi

results in

.. code-block:: python

    import math
    import sys


    def foo():
        try:
            pass
        except ImportError:
            print(sys.version)
        return math.pi


Installation
============
::

    $ pip install --upgrade autoflake


Advanced usage
==============

To allow autoflake to remove additional unused imports (other than
than those from the standard library), use the ``--imports`` option. It
accepts a comma-separated list of names::

    $ autoflake --imports=django,requests,urllib3 <filename>

To remove all unused imports (whether or not they are from the standard
library), use the ``--remove-all-unused-imports`` option.

To remove unused variables, use the ``--remove-unused-variables`` option.

Below is the full listing of options::

    usage: autoflake [-h] [-i] [-r] [--imports IMPORTS]
                     [--remove-all-unused-imports] [--remove-unused-variables]
                     [--version]
                     files [files ...]

    Removes unused imports as reported by pyflakes.

    positional arguments:
      files                 files to format

    optional arguments:
      -h, --help            show this help message and exit
      -i, --in-place        make changes to files instead of printing diffs
      -r, --recursive       drill down directories recursively
      --imports IMPORTS     by default, only unused standard library imports are
                            removed; specify a comma-separated list of additional
                            modules/packages
      --remove-all-unused-imports
                            remove all unused imports (not just those from the
                            standard library
      --remove-unused-variables
                            remove unused variables
      --version             show program's version number and exit


Tests
=====

To run the unit tests::

    $ ./test_autoflake.py

The acid test, runs against any collection of given Python files. It tests
autoflake against the files and checks how well it does by running pyflakes
on the file before and after. (This is done in memory. The actual files are
left untouched.)::

    $ ./test_acid.py --verbose
