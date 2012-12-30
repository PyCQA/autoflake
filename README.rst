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

    def foo():
        if True:
            import abc
        else:
            import subprocess
            import sys
        return math.pi

results in

.. code-block:: python

    import math

    def foo():
        if True:
            pass
        else:
            pass
        return math.pi

Installation
------------
::

    $ pip install --upgrade autoflake
