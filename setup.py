#!/usr/bin/env python
"""Setup for autoflake."""

import ast
import sys


if sys.version_info < (2, 7):
    raise SystemExit('autoflake requires Python >= 2.7')


def version():
    """Return version string."""
    with open('autoflake.py') as input_file:
        for line in input_file:
            if line.startswith('__version__'):
                return ast.parse(line).body[0].value.s


def pyflakes_installed():
    """Return True if pyflakes executable is installed."""
    import os
    import subprocess
    try:
        process = subprocess.Popen(
            ['pyflakes', os.devnull],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        process.communicate()
        return True
    except OSError:
        return False


with open('README.rst') as readme:
    setup_arguments = {
        'name': 'autoflake',
        'version': version(),
        'description': 'Removes unused imports.',
        'long_description': readme.read(),
        'license': 'Expat License',
        'author': 'Steven Myint',
        'url': 'https://github.com/myint/autoflake',
        'classifiers': ['Intended Audience :: Developers',
                        'Environment :: Console',
                        'Programming Language :: Python :: 2.7',
                        'Programming Language :: Python :: 3',
                        'License :: OSI Approved :: MIT License'],
        'keywords': 'clean,automatic,unused,import',
        'py_modules': ['autoflake'],
        'scripts': ['autoflake'],
    }


if pyflakes_installed():
    from distutils import core
    core.setup(**setup_arguments)
else:
    # Only resort to setuptools if necessary.
    import setuptools
    setuptools.setup(
        install_requires=['pyflakes'],
        **setup_arguments)
