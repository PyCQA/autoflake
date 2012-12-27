#!/usr/bin/env python
"""Setup for autoflake."""

from distutils import core


def version():
    """Return version string."""
    with open('autoflake.py') as input_file:
        for line in input_file:
            if line.startswith('__version__'):
                import ast
                return ast.literal_eval(line.split('=')[1].strip())


with open('README.rst') as readme:
    core.setup(name='autoflake',
               version=version(),
               description='Removes unused imports.',
               long_description=readme.read(),
               license='Expat License',
               author='myint',
               url='https://github.com/myint/autoflake',
               classifiers=['Intended Audience :: Developers',
                            'Environment :: Console',
                            'Programming Language :: Python :: 2.7',
                            'Programming Language :: Python :: 3',
                            'License :: OSI Approved :: MIT License'],
               keywords='clean,automatic,unused,import',
               py_modules=['autoflake'],
               scripts=['autoflake'])
