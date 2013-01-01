autoflake
=========

.. image:: https://travis-ci.org/myint/autoflake.png?branch=master
   :target: https://travis-ci.org/myint/autoflake
   :alt: Build status

Introduction
------------

*autoflake* removes unused imports from Python code. It makes use of pyflakes_
to do this.

autoflake only removes unused imports for modules that are part of the
standard library. (Other modules may have side effects that make them
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
than those from the standard library), used the ``--imports`` option. It
accepts a comma-separated list of names::

    $ autoflake --imports=django,requests,urllib3 <filename>

Installation
------------
::

    $ pip install --upgrade autoflake
