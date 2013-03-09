autoflake
=========

.. image:: https://travis-ci.org/myint/autoflake.png?branch=master
   :target: https://travis-ci.org/myint/autoflake
   :alt: Build status

Introduction
------------

*autoflake* removes unused imports from Python code. It makes use of pyflakes_
to do this.

By default, autoflake only removes unused imports for modules that are part of
the standard library. (Other modules may have side effects that make them
unsafe to remove automatically.)

autoflake also removes useless ``pass`` statements.

.. _pyflakes: http://pypi.python.org/pypi/pyflakes

Example
-------

Running autoflake on the below example::

    $ autoflake --in-place example.py

.. code-block:: python

    import math
    import re
    import os
    import random
    import multiprocessing
    import grp, pwd, platform
    import subprocess, sys

    def foo():
        if True:
            from abc import ABCMeta, WeakSet
        else:
            print(sys.version)
        return math.pi

results in

.. code-block:: python

    import math
    import sys

    def foo():
        if True:
            pass
        else:
            print(sys.version)
        return math.pi

Advanced usage
--------------

To prevent autoflake from removing certain lines, add ``NOQA`` as an
inline comment.

.. code-block:: python

    import math  # NOQA

To allow autoflake to remove additional unused imports (other than
than those from the standard library), use the ``--imports`` option. It
accepts a comma-separated list of names::

    $ autoflake --imports=django,requests,urllib3 <filename>

To remove all unused imports (whether or not they are from the standard
library), use the ``--remove-all`` option.

Below is the full listing of options::

    usage: autoflake [-h] [-i] [-r] [--imports IMPORTS] [--remove-all] [--version]
                     files [files ...]

    Removes unused imports as reported by pyflakes.

    positional arguments:
      files              files to format

    optional arguments:
      -h, --help         show this help message and exit
      -i, --in-place     make changes to files instead of printing diffs
      -r, --recursive    drill down directories recursively
      --imports IMPORTS  by default, only unused standard library imports are
                         removed; specify a comma-separated list of additional
                         modules/packages
      --remove-all       remove all unused imports (not just those from the
                         standard library
      --version          show program's version number and exit

Installation
------------
::

    $ pip install --upgrade autoflake
