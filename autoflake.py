"""Removes unused imports as reported by pyflakes."""

from __future__ import print_function

from io import StringIO
import os
import subprocess
import tempfile


__version__ = '0.0.1'


PYFLAKES_BIN = 'pyflakes'


def unused_import_line_numbers(source):
    """Yield line numbers of unused imports."""
    temp_filename = tempfile.mkstemp()[1]
    with open_with_encoding(temp_filename, encoding='utf-8', mode='w') as f:
        f.write(source)

    for line in run_pyflakes(temp_filename).splitlines():
        yield int(line.split(':')[1])

    os.remove(temp_filename)


def run_pyflakes(filename):
    """Return output of pyflakes."""
    assert ':' not in filename

    process = subprocess.Popen(
        [PYFLAKES_BIN, filename],
        stdout=subprocess.PIPE)
    return process.communicate()[0].decode('utf-8')


def filter_commented_out_code(source):
    """Yield code with unused imports removed."""
    marked_lines = list(unused_import_line_numbers(source))
    sio = StringIO(source)
    for line_number, line in enumerate(sio.readlines(), start=1):
        if line_number not in marked_lines:
            yield line


def fix_file(filename, args, standard_out):
    """Run filter_commented_out_code() on file."""
    encoding = detect_encoding(filename)
    with open_with_encoding(filename, encoding=encoding) as input_file:
        source = input_file.read()

    filtered_source = ''.join(filter_commented_out_code(source))

    if source != filtered_source:
        if args.in_place:
            with open_with_encoding(filename, mode='w',
                                    encoding=encoding) as output_file:
                output_file.write(filtered_source)
        else:
            import difflib
            diff = difflib.unified_diff(
                StringIO(source).readlines(),
                StringIO(filtered_source).readlines(),
                'before/' + filename,
                'after/' + filename)
            standard_out.write(''.join(diff))


def open_with_encoding(filename, encoding, mode='r'):
    """Return opened file with a specific encoding."""
    import io
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
