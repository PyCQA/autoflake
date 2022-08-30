# autoflake

[![Build Status](https://github.com/PyCQA/autoflake/actions/workflows/main.yaml/badge.svg?branch=master)](https://github.com/PyCQA/autoflake/actions/workflows/main.yaml)

## Introduction

_autoflake_ removes unused imports and unused variables from Python code. It
makes use of [pyflakes](https://pypi.org/pypi/pyflakes) to do this.

By default, autoflake only removes unused imports for modules that are part of
the standard library. (Other modules may have side effects that make them
unsafe to remove automatically.) Removal of unused variables is also disabled
by default.

autoflake also removes useless ``pass`` statements.

## Example

Running autoflake on the below example

```
$ autoflake --in-place --remove-unused-variables example.py
```

```python
import math
import re
import os
import random
import multiprocessing
import grp, pwd, platform
import subprocess, sys


def foo():
    from abc import ABCMeta, WeakSet
    try:
        import multiprocessing
        print(multiprocessing.cpu_count())
    except ImportError as exception:
        print(sys.version)
    return math.pi
```

results in

```python
import math
import sys


def foo():
    try:
        import multiprocessing
        print(multiprocessing.cpu_count())
    except ImportError:
        print(sys.version)
    return math.pi
```


## Installation

```
$ pip install --upgrade autoflake
```


## Advanced usage

To allow autoflake to remove additional unused imports (other than
than those from the standard library), use the ``--imports`` option. It
accepts a comma-separated list of names:

```
$ autoflake --imports=django,requests,urllib3 <filename>
```

To remove all unused imports (whether or not they are from the standard
library), use the ``--remove-all-unused-imports`` option.

To remove unused variables, use the ``--remove-unused-variables`` option.

Below is the full listing of options:

```
usage: autoflake [-h] [-c] [-r] [-j n] [--exclude globs] [--imports IMPORTS] [--expand-star-imports] [--remove-all-unused-imports] [--ignore-init-module-imports] [--remove-duplicate-keys]
                 [--remove-unused-variables] [--version] [--quiet] [-v] [--stdin-display-name STDIN_DISPLAY_NAME] [-i | -s]
                 files [files ...]

Removes unused imports and unused variables as reported by pyflakes.

positional arguments:
  files                 files to format

options:
  -h, --help            show this help message and exit
  -c, --check           return error code if changes are needed
  -r, --recursive       drill down directories recursively
  -j n, --jobs n        number of parallel jobs; match CPU count if value is 0 (default: 0)
  --exclude globs       exclude file/directory names that match these comma-separated globs
  --imports IMPORTS     by default, only unused standard library imports are removed; specify a comma-separated list of additional modules/packages
  --expand-star-imports
                        expand wildcard star imports with undefined names; this only triggers if there is only one star import in the file; this is skipped if there are any uses of `__all__` or `del` in the file
  --remove-all-unused-imports
                        remove all unused imports (not just those from the standard library)
  --ignore-init-module-imports
                        exclude __init__.py when removing unused imports
  --remove-duplicate-keys
                        remove all duplicate keys in objects
  --remove-unused-variables
                        remove unused variables
  --remove-rhs-for-unused-variables
                        remove RHS of statements when removing unused variables (unsafe)
  --version             show program's version number and exit
  --quiet               Suppress output if there are no issues
  -v, --verbose         print more verbose logs (you can repeat `-v` to make it more verbose)
  --stdin-display-name STDIN_DISPLAY_NAME
                        the name used when processing input from stdin
  -i, --in-place        make changes to files instead of printing diffs
  -s, --stdout          print changed text to stdout. defaults to true when formatting stdin, or to false otherwise
```


## Configuration

Configure default arguments using a `pyproject.toml` file:

```toml
[tool.autoflake]
check = true
imports = ["django", "requests", "urllib3"]
```

Or a `setup.cfg` file:

```ini
[autoflake]
check=true
imports=django,requests,urllib3
```

The name of the configuration parameters match the flags (e.g. use the
parameter `expand-star-imports` for the flag `--expand-star-imports`).

## Tests

To run the unit tests::

```
$ ./test_autoflake.py
```

There is also a fuzz test, which runs against any collection of given Python
files. It tests autoflake against the files and checks how well it does by
running pyflakes on the file before and after. The test fails if the pyflakes
results change for the worse. (This is done in memory. The actual files are
left untouched.)::

```
$ ./test_fuzz.py --verbose
```

## Excluding specific lines

It might be the case that you have some imports for their side effects, even
if you are not using them directly in that file.

That is common, for example, in Flask based applications. In where you import
Python modules (files) that imported a main ``app``, to have them included in
the routes.

For example:

```python
from .endpoints import role, token, user, utils
```

As those imports are not being used directly, if you are using the option
``--remove-all-unused-imports``, they would be removed.

To prevent that, without having to exclude the entire file, you can add a
``# noqa`` comment at the end of the line, like:

```python
from .endpoints import role, token, user, utils  # noqa
```

That line will instruct ``autoflake`` to let that specific line as is.


## Using [pre-commit](https://pre-commit.comn) hooks

Add the following to your `.pre-commit-config.yaml`

```yaml
-   repo: https://github.com/PyCQA/autoflake
    rev: v1.5.2
    hooks:
    -   id: autoflake
```
