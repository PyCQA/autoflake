#!/usr/bin/env python

# Copyright (C) 2012-2017 Steven Myint
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

"""Removes unused imports and unused variables as reported by pyflakes."""

from __future__ import print_function
from __future__ import unicode_literals

import ast
import difflib
import collections
import types
import pprint
import distutils.sysconfig
import fnmatch
import io
import os
import re
import signal
import sys
import tokenize

import astor

__version__ = '1.2a0'



PYTHON_SHEBANG_REGEX = re.compile(r'^#!.*\bpython[23]?\b\s*$')

MAX_PYTHON_FILE_DETECTION_BYTES = 1024

try:
    unicode
except NameError:
    unicode = str


try:
    RecursionError
except NameError:
    # Python before 3.5.
    RecursionError = RuntimeError


def load_from_wildcard(package_name):
    func_str = "import {}\n\n".format(package_name)
    func_container = compile(func_str, "<import_{}>".format(package_name), "exec")
    module_wrapped = {}
    exec(func_container, module_wrapped)
    # pprint.pprint(("Scope: ", module_wrapped))
    if "." in package_name:
        package_name = package_name.split(".")
    else:
        package_name = [package_name]

    for chunk in package_name:
        if isinstance(module_wrapped, dict):
            module_wrapped = module_wrapped[chunk]
        elif isinstance(module_wrapped, types.ModuleType):
            module_wrapped = getattr(module_wrapped, chunk)
        else:
            raise RuntimeError("Unknown type for module extraction: {}".format(type(chunk)))

    # At this point, we should have the relevant moduule imported as module_wrapped
    # Since we just want the names of it's contents, return the dir() of it
    return module_wrapped, dir(module_wrapped)

def find_wildcards(tree):
    wildcards = {}
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ImportFrom):
            imports = [tmp.name for tmp in node.names]
            if imports == ["*"]:
                mod, loaded = load_from_wildcard(node.module)
                wildcards[mod] = loaded
    return wildcards


def extract_attribute(target):
    target_in = target
    item_path = []
    if isinstance(target, ast.Name):
        return target.id
    while isinstance(target.value, ast.Attribute):
        item_path.append(target.attr)
        target = target.value
    item_path.append(target.attr)

    if isinstance(target.value, ast.Name):
        item_path.append(target.value.id)
    elif isinstance(target.value, ast.Call):
        item_path.append(extract_attribute(target.value.func))
    elif isinstance(target.value, ast.Str):
        item_path.append(target.value.s)
    elif isinstance(target.value, ast.Subscript):
        item_path.append(extract_attribute(target.value.value))
    else:
        print("Dynamic attribute! How?")
        print(ast.dump(target))
        raise RuntimeError

    # Attribute objects are unwrapped in reverse order.
    item_path.reverse()

    assert item_path, "Null path for item! Wat? Ast: {}".format(
        ast.dump(target_in))

    fqpath = ".".join(item_path)
    return fqpath

class ProtectedVisitor(ast.NodeVisitor):
    def __init__(self):
        super(ProtectedVisitor, self).__init__()
        self.assigned_names = set()
    def _extract_targets(self, target):
        if isinstance(target, ast.Name):
            self.assigned_names.add(target.id)
        elif isinstance(target, ast.Tuple):
            for sub_target in target.elts:
                self._extract_targets(sub_target)
        elif isinstance(target, ast.Attribute):
            self.assigned_names.add(extract_attribute(target))
        elif isinstance(target, ast.Subscript):
            self._extract_targets(target.value)
        else:
            raise RuntimeError("Unknown target ast structure! '{}', '{}'".format(
                    ast.dump(target), astor.to_source(target).strip()
                ))

    def visit_Assign(self, node):
        for target in node.targets:
            self._extract_targets(target)
        # print("Assignment:", ast.dump(node))
        return node
    def visit_FunctionDef(self, node):
        self.assigned_names.add(node.name)
        return node

    def extract_names(self):
        print("Found %s potential variable names!" % len(self.assigned_names))
        return list(self.assigned_names)


class WildcardVisitor(ast.NodeVisitor):
    def __init__(self, bad_contexts, protected_names):
        super(WildcardVisitor, self).__init__()
        self.bad_contexts = bad_contexts
        self.protected_names = protected_names

    def visit_Call(self, node):
        as_src = astor.to_source(node)

        fnode = node.func
        if isinstance(fnode, ast.Name):
            fname = fnode.id
            # print("Fname:", fname)
        elif isinstance(fnode, ast.Attribute):
            try:
                fname = extract_attribute(fnode)
            except RuntimeError:
                print("Wat?")
                print(as_src)
        else:
            print("Wat?")
            # print(ast.dump(node))
            print(ast.dump(node.func))

        if not "." in fname:
            if fname not in self.protected_names:
                for mod_name, funcs in self.bad_contexts.items():
                    if fname in funcs:
                        print("Should canonize? {} -> contained by: {}".format(fname.ljust(15), mod_name))
                        return
                # print(fname)
                pass

        return node

def auto_star(filename, filecontents):
    print("Processing file", filename)
    tree = compile(filecontents, filename, 'exec', ast.PyCF_ONLY_AST)
    wildcards = find_wildcards(tree)

    assignment_visitor = ProtectedVisitor()
    assignment_visitor.visit(tree)
    var_names = assignment_visitor.extract_names()

    visitor = WildcardVisitor(wildcards, var_names)
    visitor.visit(tree)

    # fixed_contents = fix_wildcards(wildcards, tree, filecontents)

    return filecontents



def fix_file(filename, args, standard_out):
    """Run fix_code() on a file."""
    encoding = detect_encoding(filename)
    with open_with_encoding(filename, encoding=encoding) as input_file:
        source = input_file.read()

    original_source = source

    if args.expand_star_imports:
        source = auto_star(filename, source)

    if original_source != source:
        if args.in_place:
            with open_with_encoding(filename, mode='w',
                                    encoding=encoding) as output_file:
                output_file.write(source)
        else:
            diff = get_diff_text(
                io.StringIO(original_source).readlines(),
                io.StringIO(source).readlines(),
                filename)
            standard_out.write(''.join(diff))


def open_with_encoding(filename, encoding, mode='r',
                       limit_byte_check=-1):
    """Return opened file with a specific encoding."""
    if not encoding:
        encoding = detect_encoding(filename, limit_byte_check=limit_byte_check)

    return io.open(filename, mode=mode, encoding=encoding,
                   newline='')  # Preserve line endings


def detect_encoding(filename, limit_byte_check=-1):
    """Return file encoding."""
    try:
        with open(filename, 'rb') as input_file:
            encoding = _detect_encoding(input_file.readline)

            # Check for correctness of encoding.
            with open_with_encoding(filename, encoding) as input_file:
                input_file.read(limit_byte_check)

        return encoding
    except (LookupError, SyntaxError, UnicodeDecodeError):
        return 'latin-1'


def _detect_encoding(readline):
    """Return file encoding."""
    try:
        from lib2to3.pgen2 import tokenize as lib2to3_tokenize
        encoding = lib2to3_tokenize.detect_encoding(readline)[0]
        return encoding
    except (LookupError, SyntaxError, UnicodeDecodeError):
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


def _split_comma_separated(string):
    """Return a set of strings."""
    return set(text.strip() for text in string.split(',') if text.strip())


def is_python_file(filename):
    """Return True if filename is Python file."""
    if filename.endswith('.py'):
        return True

    try:
        with open_with_encoding(
                filename,
                None,
                limit_byte_check=MAX_PYTHON_FILE_DETECTION_BYTES) as f:
            text = f.read(MAX_PYTHON_FILE_DETECTION_BYTES)
            if not text:
                return False
            first_line = text.splitlines()[0]
    except (IOError, IndexError):
        return False

    if not PYTHON_SHEBANG_REGEX.match(first_line):
        return False

    return True


def match_file(filename, exclude):
    """Return True if file is okay for modifying/recursing."""
    base_name = os.path.basename(filename)

    if base_name.startswith('.'):
        return False

    for pattern in exclude:
        if fnmatch.fnmatch(base_name, pattern):
            return False
        if fnmatch.fnmatch(filename, pattern):
            return False

    if not os.path.isdir(filename) and not is_python_file(filename):
        return False

    return True


def find_files(filenames, recursive, exclude):
    """Yield filenames."""
    while filenames:
        name = filenames.pop(0)
        if recursive and os.path.isdir(name):
            for root, directories, children in os.walk(name):
                filenames += [os.path.join(root, f) for f in children
                              if match_file(os.path.join(root, f),
                                            exclude)]
                directories[:] = [d for d in directories
                                  if match_file(os.path.join(root, d),
                                                exclude)]
        else:
            yield name


def _main(argv, standard_out, standard_error):
    """Return exit status.

    0 means no error.
    """
    import argparse
    parser = argparse.ArgumentParser(description=__doc__, prog='autostar')
    parser.add_argument('-i', '--in-place', action='store_true',
                        help='make changes to files instead of printing diffs')
    parser.add_argument('-r', '--recursive', action='store_true',
                        help='drill down directories recursively')
    parser.add_argument('--exclude', metavar='globs',
                        help='exclude file/directory names that match these '
                             'comma-separated globs')
    parser.add_argument('--expand-star-imports', action='store_true',
                        help='expand wildcard star imports with undefined '
                             'names')
    parser.add_argument('--version', action='version',
                        version='%(prog)s ' + __version__)
    parser.add_argument('files', nargs='+', help='files to format')

    args = parser.parse_args(argv[1:])


    if args.exclude:
        args.exclude = _split_comma_separated(args.exclude)
    else:
        args.exclude = set([])

    filenames = list(set(args.files))
    failure = False
    for name in find_files(filenames, args.recursive, args.exclude):
        try:
            fix_file(name, args=args, standard_out=standard_out)
        except IOError as exception:
            print(unicode(exception), file=standard_error)
            failure = True

    return 1 if failure else 0


def main():
    """Command-line entry point."""
    try:
        # Exit on broken pipe.
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    except AttributeError:  # pragma: no cover
        # SIGPIPE is not available on Windows.
        pass

    try:
        return _main(sys.argv,
                     standard_out=sys.stdout,
                     standard_error=sys.stderr)
    except KeyboardInterrupt:  # pragma: no cover
        return 2  # pragma: no cover


if __name__ == '__main__':
    sys.exit(main())
