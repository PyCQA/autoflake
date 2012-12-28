#!/usr/bin/env python
"""Test that autoflake runs without crashing on various Python files."""

import os
import sys
import subprocess


ROOT_PATH = os.path.abspath(os.path.dirname(__file__))
AUTOFLAKE_BIN = os.path.join(ROOT_PATH, 'autoflake')

import autoflake

if sys.stdout.isatty():
    YELLOW = '\033[33m'
    END = '\033[0m'
else:
    YELLOW = ''
    END = ''


def colored(text, color):
    """Return color coded text."""
    return color + text + END


def pyflakes_count(filename):
    """Return pyflakes error count."""
    # File location so we need to filter out __all__ complaints.
    return len([line for line in autoflake.run_pyflakes(filename).splitlines()
                if '__all__' not in line])


def run(filename, verbose=False):
    """Run autoflake on file at filename.

    Return True on success.

    """
    import test_autoflake
    with test_autoflake.temporary_directory() as temp_directory:
        temp_filename = os.path.join(temp_directory,
                                     os.path.basename(filename))
        import shutil
        shutil.copyfile(filename, temp_filename)

        if 0 != subprocess.call([AUTOFLAKE_BIN, '--in-place', temp_filename]):
            sys.stderr.write('autoflake crashed on ' + filename + '\n')
            return False

        try:
            if check_syntax(filename):
                try:
                    check_syntax(temp_filename, raise_error=True)
                except (SyntaxError, TypeError,
                        UnicodeDecodeError) as exception:
                    sys.stderr.write('autoflake broke ' + filename + '\n' +
                                     str(exception) + '\n')
                    return False

            before_count = pyflakes_count(filename)
            after_count = pyflakes_count(temp_filename)

            if verbose:
                print('(before, after):', (before_count, after_count))

            if after_count > before_count:
                sys.stderr.write('autoflake made ' + filename + ' worse\n')
                return False
        except IOError as exception:
            sys.stderr.write(str(exception) + '\n')

    return True


def check_syntax(filename, raise_error=False):
    """Return True if syntax is okay."""
    with autoflake.open_with_encoding(
            filename,
            encoding=autoflake.detect_encoding(filename)) as input_file:
        try:
            compile(input_file.read(), '<string>', 'exec')
            return True
        except (SyntaxError, TypeError, UnicodeDecodeError):
            if raise_error:
                raise
            else:
                return False


def process_args():
    """Return processed arguments (options and positional arguments)."""
    import argparse
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--timeout',
        help='stop testing additional files after this amount of time '
             '(default: %default)',
        default=-1,
        type=float)

    parser.add_argument('--verbose', action='store_true',
                        help='print verbose messages')

    parser.add_argument('files', nargs='*', help='files to format')

    return parser.parse_args()


class TimeoutException(Exception):

    """Timeout exception."""


def timeout(_, __):
    raise TimeoutException()


def check(args):
    """Run recursively run autoflake on directory of files.

    Return False if the fix results in broken syntax.

    """
    if args.files:
        dir_paths = args.files
    else:
        dir_paths = [path for path in sys.path
                     if os.path.isdir(path)]

    filenames = dir_paths
    completed_filenames = set()

    try:
        import signal
        if args.timeout > 0:
            signal.signal(signal.SIGALRM, timeout)
            signal.alarm(int(args.timeout))

        while filenames:
            name = os.path.realpath(filenames.pop(0))
            if name in completed_filenames:
                sys.stderr.write(
                    colored('--->  Skipping previously tested ' + name + '\n',
                            YELLOW))
                continue
            else:
                completed_filenames.update(name)

            try:
                is_directory = os.path.isdir(name)
            except UnicodeEncodeError:
                continue

            if is_directory:
                for root, directories, children in os.walk(name):
                    filenames += [os.path.join(root, f) for f in children
                                  if f.endswith('.py') and
                                  not f.startswith('.')]
                    for d in directories:
                        if d.startswith('.'):
                            directories.remove(d)
            else:
                verbose_message = '--->  Testing with '
                try:
                    verbose_message += name
                except UnicodeEncodeError:
                    verbose_message += '...'
                sys.stderr.write(colored(verbose_message + '\n', YELLOW))

                if not run(os.path.join(name), verbose=args.verbose):
                    return False
    except TimeoutException:
        sys.stderr.write('Timed out\n')
    finally:
        if args.timeout > 0:
            signal.alarm(0)

    return True


def main():
    """Run main."""
    return 0 if check(process_args()) else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
