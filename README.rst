autoflake
=========

.. image:: https://secure.travis-ci.org/myint/autoflake.png
   :target: https://secure.travis-ci.org/myint/autoflake
   :alt: Build status

Introduction
------------

*autoflake* removes unused imports from Python code. It makes use of pyflakes_
to do this.

autoflake only removes unused standard modules imports. This is necessary
since other modules may have side effecs, making them unsafe to remove
automatically.

.. _pyflakes: http://pypi.python.org/pypi/pyflakes

Example
-------

::

    $ autoflake --in-place example.py

.. code-block:: python

   import math
   import re

   def foo():
       import abc
       math.pi

results in

.. code-block:: python

   import math

   def foo():
       math.pi
