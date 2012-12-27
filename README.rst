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

.. _pyflakes: http://pypi.python.org/pypi/pyflakes

Example
-------

::

    $ autoflake --in-place example.py

.. code-block:: python

    import math
    import re
    import os
    import random
    import multiprocessing

    def foo():
        try:
            import abc
        except ImportError:
            import subprocess
            import sys
        return math.pi

results in

.. code-block:: python

    import math

    def foo():
        try:
            pass
        except ImportError:
            pass
        return math.pi

Limitations
-----------

autoflake currently only removes simple import statements. It will not
remove more complex statements such as ``from os import path, sep``.
