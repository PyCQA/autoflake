"""Removes unused imports as reported by pyflakes."""

from __future__ import print_function

import io
import os


__version__ = '0.1.1'


PYFLAKES_BIN = 'pyflakes'


class MissingExecutableException(Exception):

    """Raised when executable is missing."""


def standard_package_names():
    """Yield list of standard module names."""
    from distutils import sysconfig
    for name in os.listdir(sysconfig.get_python_lib(standard_lib=True)):

        if name.startswith('_'):
            continue

        extension = '.py'
        if name.endswith(extension):
            yield name[:-len(extension)]
        else:
            yield name


IMPORTS_WITH_SIDE_EFFECTS = {'rlcompleter'}

BINARY_IMPORTS = {'datetime', 'io', 'json', 'multiprocessing', 'parser', 'sys',
                  'time'}

SAFE_IMPORTS = (set(standard_package_names()) -
                IMPORTS_WITH_SIDE_EFFECTS |
                BINARY_IMPORTS)


def unused_import_line_numbers(source):
    """Yield line numbers of unused imports."""
    import tempfile
    (_temp_open_file, temp_filename) = tempfile.mkstemp()
    os.close(_temp_open_file)

    with open_with_encoding(temp_filename, encoding='utf-8', mode='w') as f:
        f.write(source)

    for line in run_pyflakes(temp_filename).splitlines():
        if line.rstrip().endswith('imported but unused'):
            yield int(line.split(':')[1])

    os.remove(temp_filename)


def run_pyflakes(filename):
    """Return output of pyflakes."""
    assert ':' not in filename

    import subprocess
    try:
        process = subprocess.Popen(
            [PYFLAKES_BIN, filename],
            stdout=subprocess.PIPE)
        return process.communicate()[0].decode('utf-8')
    except OSError:
        raise MissingExecutableException()


def extract_package_name(line):
    """Return package name in import statement."""
    assert ',' not in line
    assert '\\' not in line

    if line.lstrip().startswith('import'):
        word = line.split()[1]
    else:
        assert line.lstrip().startswith('from')
        word = line.split()[1]

    package = word.split('.')[0]
    assert ' ' not in package

    return package


def filter_code(source):
    """Yield code with unused imports removed."""
    marked_lines = list(unused_import_line_numbers(source))
    sio = io.StringIO(source)
    for line_number, line in enumerate(sio.readlines(), start=1):
        if (line_number in marked_lines and
                ',' not in line and
                '\\' not in line):
            package = extract_package_name(line)
            if package not in SAFE_IMPORTS:
                yield line
            elif line.lstrip() != line:
                # Remove indented unused import.
                yield indentation(line) + 'pass' + line_ending(line)
            else:
                # Discard unused import line.
                pass
        else:
            yield line


def useless_pass_line_numbers(source):
    """Yield line numbers of commented-out code."""
    sio = io.StringIO(source)
    import tokenize
    try:
        previous_token_type = None
        for token in tokenize.generate_tokens(sio.readline):
            token_type = token[0]
            start_row = token[2][0]
            line = token[4]

            is_pass = (token_type == tokenize.NAME and line.strip() == 'pass')

            # TODO: Leading "pass".

            # Trailing "pass".
            if is_pass and previous_token_type != tokenize.INDENT:
                yield start_row

            previous_token_type = token_type
    except (tokenize.TokenError, IndentationError):
        pass


def filter_useless_pass(source):
    """Yield code with useless "pass" lines removed."""
    marked_lines = list(useless_pass_line_numbers(source))
    sio = io.StringIO(source)
    for line_number, line in enumerate(sio.readlines(), start=1):
        if line_number not in marked_lines:
            yield line


def indentation(line):
    """Return leading whitespace."""
    if line.strip():
        non_whitespace_index = len(line) - len(line.lstrip())
        return line[:non_whitespace_index]
    else:
        return ''


def line_ending(line):
    """Return line ending."""
    non_whitespace_index = len(line.rstrip()) - len(line)
    return line[non_whitespace_index:]


def fix_file(filename, args, standard_out):
    """Run filter_code() on file."""
    encoding = detect_encoding(filename)
    with open_with_encoding(filename, encoding=encoding) as input_file:
        source = input_file.read()

    original_source = source

    filtered_source = None
    while True:
        filtered_source = ''.join(filter_code(source))
        if filtered_source == source:
            break
        source = filtered_source

    if original_source != filtered_source:
        if args.in_place:
            with open_with_encoding(filename, mode='w',
                                    encoding=encoding) as output_file:
                output_file.write(filtered_source)
        else:
            import difflib
            diff = difflib.unified_diff(
                io.StringIO(original_source).readlines(),
                io.StringIO(filtered_source).readlines(),
                'before/' + filename,
                'after/' + filename)
            standard_out.write(''.join(diff))


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


def main(argv, standard_out, standard_error):
    """Main entry point."""
    import argparse
    parser = argparse.ArgumentParser(description=__doc__, prog='autoflake')
    parser.add_argument('-i', '--in-place', action='store_true',
                        help='make changes to files instead of printing diffs')
    parser.add_argument('-r', '--recursive', action='store_true',
                        help='drill down directories recursively')
    parser.add_argument('--version', action='version', version=__version__)
    parser.add_argument('files', nargs='+', help='files to format')

    args = parser.parse_args(argv[1:])

    filenames = list(set(args.files))
    while filenames:
        name = filenames.pop(0)
        if args.recursive and os.path.isdir(name):
            for root, directories, children in os.walk(name):
                filenames += [os.path.join(root, f) for f in children
                              if f.endswith('.py') and
                              not f.startswith('.')]
                for d in directories:
                    if d.startswith('.'):
                        directories.remove(d)
        else:
            try:
                fix_file(name, args=args, standard_out=standard_out)
            except IOError as exception:
                print(exception, file=standard_error)
