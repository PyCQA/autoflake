# Copyright (C) 2012-2013 Steven Myint
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""Removes unused imports as reported by pyflakes."""

from __future__ import print_function
from __future__ import unicode_literals

import difflib
import io
import os
import tokenize

import pyflakes.api
import pyflakes.messages
import pyflakes.reporter


__version__ = '0.3.2'


PYFLAKES_BIN = 'pyflakes'


try:
    unicode
except NameError:
    unicode = str


def standard_package_names():
    """Yield list of standard module names."""
    from distutils import sysconfig
    path = sysconfig.get_python_lib(standard_lib=True)

    for name in (
            frozenset(os.listdir(path)) |
            frozenset(os.listdir(os.path.join(path, 'lib-dynload')))):

        if name.startswith('_') or '-' in name:
            continue

        if '.' in name and name.rsplit('.')[-1] not in ['so', 'py', 'pyc']:
            continue

        yield name.split('.')[0]


IMPORTS_WITH_SIDE_EFFECTS = {'antigravity', 'rlcompleter', 'this'}

# In case they are built into CPython.
BINARY_IMPORTS = {'datetime', 'grp', 'io', 'json', 'math', 'multiprocessing',
                  'parser', 'pwd', 'string', 'operator', 'os', 'sys', 'time'}

SAFE_IMPORTS = (frozenset(standard_package_names()) -
                IMPORTS_WITH_SIDE_EFFECTS |
                BINARY_IMPORTS)


def unused_import_line_numbers(source):
    """Yield line numbers of unused imports."""
    for message in check(source):
        if isinstance(message, pyflakes.messages.UnusedImport):
            yield message.lineno


def check(source):
    """Return messages from pyflakes."""
    reporter = ListReporter()
    try:
        pyflakes.api.check(source, filename='<string>', reporter=reporter)
    except UnicodeDecodeError:
        pass
    return reporter.messages


class StubFile(object):

    """Stub out file for pyflakes."""

    def write(self, *_):
        """Stub out write()."""


class ListReporter(pyflakes.reporter.Reporter):

    """Accumulate messages in messages list."""

    def __init__(self):
        """Initialize.

        Ignore errors from Reporter.

        """
        ignore = StubFile()
        pyflakes.reporter.Reporter.__init__(self, ignore, ignore)
        self.messages = []

    def flake(self, message):
        """Override Reporter.flake()."""
        self.messages.append(message)


def extract_package_name(line):
    """Return package name in import statement."""
    assert '\\' not in line
    assert '(' not in line
    assert ')' not in line
    assert ';' not in line

    if line.lstrip().startswith(('import', 'from')):
        word = line.split()[1]
    else:
        # Ignore doctests.
        return None

    package = word.split('.')[0]
    assert ' ' not in package

    return package


def multiline_import(line, previous_line=''):
    """Return True if import is spans multiples lines."""
    for symbol in '\\();:':
        if symbol in line:
            return True

    return previous_line.rstrip().endswith('\\')


def break_up_import(line):
    """Return line with imports on separate lines."""
    assert '\\' not in line
    assert '(' not in line
    assert ')' not in line
    assert ';' not in line

    newline = get_line_ending(line)
    if not newline:
        return line

    import re
    (indentation, imports) = re.split(pattern=r'\bimport\b',
                                      string=line, maxsplit=1)

    if '#' in imports:
        (imports, comment) = imports.split('#', 1)
        comment = '  # ' + comment.strip()
    else:
        comment = ''

    indentation += 'import '
    assert newline

    return ''.join([indentation + i.strip() + comment + newline
                    for i in imports.split(',')])


def filter_code(source, additional_imports=None, remove_all=False):
    """Yield code with unused imports removed."""
    imports = SAFE_IMPORTS
    if additional_imports:
        imports |= frozenset(additional_imports)
    del additional_imports

    marked_lines = frozenset(unused_import_line_numbers(source))
    sio = io.StringIO(source)
    previous_line = ''
    for line_number, line in enumerate(sio.readlines(), start=1):
        if line_number in marked_lines and not multiline_import(line,
                                                                previous_line):
            if line.strip().lower().endswith('# noqa'):
                yield line
            elif ',' in line:
                yield break_up_import(line)
            else:
                package = extract_package_name(line)
                if not remove_all and package not in imports:
                    yield line
                elif line.lstrip() != line:
                    # Remove indented unused import.
                    yield (get_indentation(line) +
                           'pass' +
                           get_line_ending(line))
                # Otherwise, discard unused import line.
        else:
            yield line

        previous_line = line


def useless_pass_line_numbers(source):
    """Yield line numbers of unneeded "pass" statements."""
    sio = io.StringIO(source)
    previous_token_type = None
    last_pass_row = None
    last_pass_indentation = None
    previous_line = ''
    for token in tokenize.generate_tokens(sio.readline):
        token_type = token[0]
        start_row = token[2][0]
        line = token[4]

        is_pass = (token_type == tokenize.NAME and line.strip() == 'pass')

        # Leading "pass".
        if (start_row - 1 == last_pass_row and
                get_indentation(line) == last_pass_indentation and
                token_type == tokenize.NAME and
                not is_pass):
            yield start_row - 1

        if is_pass:
            last_pass_row = start_row
            last_pass_indentation = get_indentation(line)

        # Trailing "pass".
        if (is_pass and
                previous_token_type != tokenize.INDENT and
                not previous_line.rstrip().endswith('\\')):
            yield start_row

        previous_token_type = token_type
        previous_line = line


def filter_useless_pass(source):
    """Yield code with useless "pass" lines removed."""
    try:
        marked_lines = frozenset(useless_pass_line_numbers(source))
    except (tokenize.TokenError, IndentationError):
        marked_lines = frozenset()

    sio = io.StringIO(source)
    for line_number, line in enumerate(sio.readlines(), start=1):
        if line_number not in marked_lines:
            yield line


def get_indentation(line):
    """Return leading whitespace."""
    if line.strip():
        non_whitespace_index = len(line) - len(line.lstrip())
        return line[:non_whitespace_index]
    else:
        return unicode()


def get_line_ending(line):
    """Return line ending."""
    non_whitespace_index = len(line.rstrip()) - len(line)
    if not non_whitespace_index:
        return ''
    else:
        return line[non_whitespace_index:]


def fix_code(source, additional_imports=None, remove_all=False):
    """Return code with all filtering run on it."""
    if not source:
        return source

    filtered_source = None
    while True:
        filtered_source = unicode().join(
            filter_useless_pass(unicode().join(
                filter_code(source,
                            additional_imports=additional_imports,
                            remove_all=remove_all))))
        if filtered_source == source:
            break
        source = filtered_source

    return filtered_source


def fix_file(filename, args, standard_out):
    """Run fix_code() on a file."""
    encoding = detect_encoding(filename)
    with open_with_encoding(filename, encoding=encoding) as input_file:
        source = input_file.read()

    original_source = source

    filtered_source = fix_code(
        source,
        additional_imports=args.imports.split(',') if args.imports else None,
        remove_all=args.remove_all)

    if original_source != filtered_source:
        if args.in_place:
            with open_with_encoding(filename, mode='w',
                                    encoding=encoding) as output_file:
                output_file.write(filtered_source)
        else:
            diff = get_diff_text(
                io.StringIO(original_source).readlines(),
                io.StringIO(filtered_source).readlines(),
                filename)
            standard_out.write(unicode().join(diff))


def open_with_encoding(filename, encoding, mode='r'):
    """Return opened file with a specific encoding."""
    return io.open(filename, mode=mode, encoding=encoding,
                   newline='')  # Preserve line endings


def detect_encoding(filename):
    """Return file encoding."""
    try:
        with open(filename, 'rb') as input_file:
            from lib2to3.pgen2 import tokenize as lib2to3_tokenize
            encoding = lib2to3_tokenize.detect_encoding(input_file.readline)[0]

            # Check for correctness of encoding.
            with open_with_encoding(filename, encoding) as input_file:
                input_file.read()

        return encoding
    except (SyntaxError, LookupError, UnicodeDecodeError):
        return 'latin-1'


def get_diff_text(old, new, filename):
    """Return text of unified diff between old and new."""
    newline = '\n'
    diff = difflib.unified_diff(
        old, new,
        'original/' + filename,
        'fixed/' + filename,
        lineterm=newline)

    text = ''
    for line in diff:
        text += line

        # Work around missing newline (http://bugs.python.org/issue2142).
        if not line.endswith(newline):
            text += newline + r'\ No newline at end of file' + newline

    return text


def main(argv, standard_out, standard_error):
    """Return 0 on success."""
    import argparse
    parser = argparse.ArgumentParser(description=__doc__, prog='autoflake')
    parser.add_argument('-i', '--in-place', action='store_true',
                        help='make changes to files instead of printing diffs')
    parser.add_argument('-r', '--recursive', action='store_true',
                        help='drill down directories recursively')
    parser.add_argument('--imports',
                        help='by default, only unused standard library '
                             'imports are removed; specify a comma-separated '
                             'list of additional modules/packages')
    parser.add_argument('--remove-all', action='store_true',
                        help='remove all unused imports (not just those from '
                             'the standard library')
    parser.add_argument('--version', action='version',
                        version='%(prog)s ' + __version__)
    parser.add_argument('files', nargs='+', help='files to format')

    args = parser.parse_args(argv[1:])

    if args.remove_all and args.imports:
        print(unicode('Using both --remove-all and --imports is redundant'),
              file=standard_error)
        return 1

    filenames = list(set(args.files))
    while filenames:
        name = filenames.pop(0)
        if args.recursive and os.path.isdir(name):
            for root, directories, children in os.walk(name):
                filenames += [os.path.join(root, f) for f in children
                              if f.endswith('.py') and
                              not f.startswith('.')]
                directories[:] = [d for d in directories
                                  if not d.startswith('.')]
        else:
            try:
                fix_file(name, args=args, standard_out=standard_out)
            except IOError as exception:
                print(unicode(exception), file=standard_error)
