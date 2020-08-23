#!/usr/bin/env python

# Copyright (C) 2012-2019 Steven Myint
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
import distutils.sysconfig
import fnmatch
import io
import os
import re
import signal
import string
import sys
import tokenize

import pyflakes.api
import pyflakes.messages
import pyflakes.reporter


__version__ = '1.3.1'


ATOMS = frozenset([tokenize.NAME, tokenize.NUMBER, tokenize.STRING])

EXCEPT_REGEX = re.compile(r'^\s*except [\s,()\w]+ as \w+:$')
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


def standard_paths():
    """Yield paths to standard modules."""
    for is_plat_spec in [True, False]:

        # Yield lib paths.
        path = distutils.sysconfig.get_python_lib(standard_lib=True,
                                                  plat_specific=is_plat_spec)
        for name in os.listdir(path):
            yield name

        # Yield lib-dynload paths.
        dynload_path = os.path.join(path, 'lib-dynload')
        if os.path.isdir(dynload_path):
            for name in os.listdir(dynload_path):
                yield name


def standard_package_names():
    """Yield standard module names."""
    for name in standard_paths():
        if name.startswith('_') or '-' in name:
            continue

        if '.' in name and not name.endswith(("so", "py", "pyc")):
            continue

        yield name.split('.')[0]


IMPORTS_WITH_SIDE_EFFECTS = {'antigravity', 'rlcompleter', 'this'}

# In case they are built into CPython.
BINARY_IMPORTS = {'datetime', 'grp', 'io', 'json', 'math', 'multiprocessing',
                  'parser', 'pwd', 'string', 'operator', 'os', 'sys', 'time'}

SAFE_IMPORTS = (frozenset(standard_package_names()) -
                IMPORTS_WITH_SIDE_EFFECTS |
                BINARY_IMPORTS)


def unused_import_line_numbers(messages):
    """Yield line numbers of unused imports."""
    for message in messages:
        if isinstance(message, pyflakes.messages.UnusedImport):
            yield message.lineno


def unused_import_module_name(messages):
    """Yield line number and module name of unused imports."""
    pattern = r'\'(.+?)\''
    for message in messages:
        if isinstance(message, pyflakes.messages.UnusedImport):
            module_name = re.search(pattern, str(message))
            module_name = module_name.group()[1:-1]
            if module_name:
                yield (message.lineno, module_name)


def star_import_used_line_numbers(messages):
    """Yield line number of star import usage."""
    for message in messages:
        if isinstance(message, pyflakes.messages.ImportStarUsed):
            yield message.lineno


def star_import_usage_undefined_name(messages):
    """Yield line number, undefined name, and its possible origin module."""
    for message in messages:
        if isinstance(message, pyflakes.messages.ImportStarUsage):
            undefined_name = message.message_args[0]
            module_name = message.message_args[1]
            yield (message.lineno, undefined_name, module_name)


def unused_variable_line_numbers(messages):
    """Yield line numbers of unused variables."""
    for message in messages:
        if isinstance(message, pyflakes.messages.UnusedVariable):
            yield message.lineno


def duplicate_key_line_numbers(messages, source):
    """Yield line numbers of duplicate keys."""
    messages = [
        message for message in messages
        if isinstance(message, pyflakes.messages.MultiValueRepeatedKeyLiteral)]

    if messages:
        # Filter out complex cases. We don't want to bother trying to parse
        # this stuff and get it right. We can do it on a key-by-key basis.

        key_to_messages = create_key_to_messages_dict(messages)

        lines = source.split('\n')

        for (key, messages) in key_to_messages.items():
            good = True
            for message in messages:
                line = lines[message.lineno - 1]
                key = message.message_args[0]

                if not dict_entry_has_key(line, key):
                    good = False

            if good:
                for message in messages:
                    yield message.lineno


def create_key_to_messages_dict(messages):
    """Return dict mapping the key to list of messages."""
    dictionary = collections.defaultdict(lambda: [])
    for message in messages:
        dictionary[message.message_args[0]].append(message)
    return dictionary


def check(source):
    """Return messages from pyflakes."""
    if sys.version_info[0] == 2 and isinstance(source, unicode):
        # Convert back to original byte string encoding, otherwise pyflakes
        # call to compile() will complain. See PEP 263. This only affects
        # Python 2.
        try:
            source = source.encode('utf-8')
        except UnicodeError:  # pragma: no cover
            return []

    reporter = ListReporter()
    try:
        pyflakes.api.check(source, filename='<string>', reporter=reporter)
    except (AttributeError, RecursionError, UnicodeDecodeError):
        pass
    return reporter.messages


class StubFile(object):
    """Stub out file for pyflakes."""

    def write(self, *_):
        """Stub out."""


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
        """Accumulate messages."""
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
    for symbol in '()':
        if symbol in line:
            return True

    return multiline_statement(line, previous_line)


def multiline_statement(line, previous_line=''):
    """Return True if this is part of a multiline statement."""
    for symbol in '\\:;':
        if symbol in line:
            return True

    sio = io.StringIO(line)
    try:
        list(tokenize.generate_tokens(sio.readline))
        return previous_line.rstrip().endswith('\\')
    except (SyntaxError, tokenize.TokenError):
        return True


class PendingFix(object):
    """Allows a rewrite operation to span multiple lines.

    In the main rewrite loop, every time a helper function returns a
    ``PendingFix`` object instead of a string, this object will be called
    with the following line.
    """

    def __init__(self, line):
        """Analyse and store the first line."""
        self.accumulator = collections.deque([line])

    def __call__(self, line):
        """Process line considering the accumulator.

        Return self to keep processing the following lines or a string
        with the final result of all the lines processed at once.
        """
        raise NotImplementedError("Abstract method needs to be overwritten")


def _valid_char_in_line(char, line):
    """Return True if a char appears in the line and is not commented."""
    comment_index = line.find('#')
    char_index = line.find(char)
    valid_char_in_line = (
        char_index >= 0 and
        (comment_index > char_index or comment_index < 0)
    )
    return valid_char_in_line


def _top_module(module_name):
    """Return the name of the top level module in the hierarchy."""
    if module_name[0] == '.':
        return '%LOCAL_MODULE%'
    return module_name.split('.')[0]


def _modules_to_remove(unused_modules, safe_to_remove=SAFE_IMPORTS):
    """Discard unused modules that are not safe to remove from the list."""
    return [x for x in unused_modules if _top_module(x) in safe_to_remove]


def _segment_module(segment):
    """Extract the module identifier inside the segment.

    It might be the case the segment does not have a module (e.g. is composed
    just by a parenthesis or line continuation and whitespace). In this
    scenario we just keep the segment... These characters are not valid in
    identifiers, so they will never be contained in the list of unused modules
    anyway.
    """
    return segment.strip(string.whitespace + ',\\()') or segment


class FilterMultilineImport(PendingFix):
    """Remove unused imports from multiline import statements.

    This class handles both the cases: "from imports" and "direct imports".

    Some limitations exist (e.g. imports with comments, lines joined by ``;``,
    etc). In these cases, the statement is left unchanged to avoid problems.
    """

    IMPORT_RE = re.compile(r'\bimport\b\s*')
    INDENTATION_RE = re.compile(r'^\s*')
    BASE_RE = re.compile(r'\bfrom\s+([^ ]+)')
    SEGMENT_RE = re.compile(
        r'([^,\s]+(?:[\s\\]+as[\s\\]+[^,\s]+)?[,\s\\)]*)', re.M)
    # ^ module + comma + following space (including new line and continuation)
    IDENTIFIER_RE = re.compile(r'[^,\s]+')

    def __init__(self, line, unused_module=(), remove_all_unused_imports=False,
                 safe_to_remove=SAFE_IMPORTS, previous_line=''):
        """Receive the same parameters as ``filter_unused_import``."""
        self.remove = unused_module
        self.parenthesized = '(' in line
        self.from_, imports = self.IMPORT_RE.split(line, maxsplit=1)
        match = self.BASE_RE.search(self.from_)
        self.base = match.group(1) if match else None
        self.give_up = False

        if not remove_all_unused_imports:
            if self.base and _top_module(self.base) not in safe_to_remove:
                self.give_up = True
            else:
                self.remove = _modules_to_remove(self.remove, safe_to_remove)

        if '\\' in previous_line:
            # Ignore tricky things like "try: \<new line> import" ...
            self.give_up = True

        self.analyze(line)

        PendingFix.__init__(self, imports)

    def is_over(self, line=None):
        """Return True if the multiline import statement is over."""
        line = line or self.accumulator[-1]

        if self.parenthesized:
            return _valid_char_in_line(')', line)

        return not _valid_char_in_line('\\', line)

    def analyze(self, line):
        """Decide if the statement will be fixed or left unchanged."""
        if any(ch in line for ch in ';:#'):
            self.give_up = True

    def fix(self, accumulated):
        """Given a collection of accumulated lines, fix the entire import."""
        old_imports = ''.join(accumulated)
        ending = get_line_ending(old_imports)
        # Split imports into segments that contain the module name +
        # comma + whitespace and eventual <newline> \ ( ) chars
        segments = [x for x in self.SEGMENT_RE.findall(old_imports) if x]
        modules = [_segment_module(x) for x in segments]
        keep = _filter_imports(modules, self.base, self.remove)

        # Short-circuit if no import was discarded
        if len(keep) == len(segments):
            return self.from_ + 'import ' + ''.join(accumulated)

        fixed = ''
        if keep:
            # Since it is very difficult to deal with all the line breaks and
            # continuations, let's use the code layout that already exists and
            # just replace the module identifiers inside the first N-1 segments
            # + the last segment
            templates = list(zip(modules, segments))
            templates = templates[:len(keep)-1] + templates[-1:]
            # It is important to keep the last segment, since it might contain
            # important chars like `)`
            fixed = ''.join(
                template.replace(module, keep[i])
                for i, (module, template) in enumerate(templates)
            )

            # Fix the edge case: inline parenthesis + just one surviving import
            if self.parenthesized and any(ch not in fixed for ch in '()'):
                fixed = fixed.strip(string.whitespace + '()') + ending

        # Replace empty imports with a "pass" statement
        empty = len(fixed.strip(string.whitespace + '\\(),')) < 1
        if empty:
            indentation = self.INDENTATION_RE.search(self.from_).group(0)
            return indentation + 'pass' + ending

        return self.from_ + 'import ' + fixed

    def __call__(self, line=None):
        """Accumulate all the lines in the import and then trigger the fix."""
        if line:
            self.accumulator.append(line)
            self.analyze(line)
        if not self.is_over(line):
            return self
        if self.give_up:
            return self.from_ + 'import ' + ''.join(self.accumulator)

        return self.fix(self.accumulator)


def _filter_imports(imports, parent=None, unused_module=()):
    # We compare full module name (``a.module`` not `module`) to
    # guarantee the exact same module as detected from pyflakes.
    sep = '' if parent and parent[-1] == '.' else '.'

    def full_name(name):
        return name if parent is None else parent + sep + name

    return [x for x in imports if full_name(x) not in unused_module]


def filter_from_import(line, unused_module):
    """Parse and filter ``from something import a, b, c``.

    Return line without unused import modules, or `pass` if all of the
    module in import is unused.
    """
    (indentation, imports) = re.split(pattern=r'\bimport\b',
                                      string=line, maxsplit=1)
    base_module = re.search(pattern=r'\bfrom\s+([^ ]+)',
                            string=indentation).group(1)

    imports = re.split(pattern=r'\s*,\s*', string=imports.strip())
    filtered_imports = _filter_imports(imports, base_module, unused_module)

    # All of the import in this statement is unused
    if not filtered_imports:
        return get_indentation(line) + 'pass' + get_line_ending(line)

    indentation += 'import '

    return (
        indentation +
        ', '.join(sorted(filtered_imports)) +
        get_line_ending(line))


def break_up_import(line):
    """Return line with imports on separate lines."""
    assert '\\' not in line
    assert '(' not in line
    assert ')' not in line
    assert ';' not in line
    assert '#' not in line
    assert not line.lstrip().startswith('from')

    newline = get_line_ending(line)
    if not newline:
        return line

    (indentation, imports) = re.split(pattern=r'\bimport\b',
                                      string=line, maxsplit=1)

    indentation += 'import '
    assert newline

    return ''.join([indentation + i.strip() + newline
                    for i in sorted(imports.split(','))])


def filter_code(source, additional_imports=None,
                expand_star_imports=False,
                remove_all_unused_imports=False,
                remove_duplicate_keys=False,
                remove_unused_variables=False,
                ignore_init_module_imports=False,
                ):
    """Yield code with unused imports removed."""
    imports = SAFE_IMPORTS
    if additional_imports:
        imports |= frozenset(additional_imports)
    del additional_imports

    messages = check(source)

    if ignore_init_module_imports:
        marked_import_line_numbers = frozenset()
    else:
        marked_import_line_numbers = frozenset(
            unused_import_line_numbers(messages))
    marked_unused_module = collections.defaultdict(lambda: [])
    for line_number, module_name in unused_import_module_name(messages):
        marked_unused_module[line_number].append(module_name)

    if expand_star_imports and not (
        # See explanations in #18.
        re.search(r'\b__all__\b', source) or
        re.search(r'\bdel\b', source)
    ):
        marked_star_import_line_numbers = frozenset(
            star_import_used_line_numbers(messages))
        if len(marked_star_import_line_numbers) > 1:
            # Auto expanding only possible for single star import
            marked_star_import_line_numbers = frozenset()
        else:
            undefined_names = []
            for line_number, undefined_name, _ \
                    in star_import_usage_undefined_name(messages):
                undefined_names.append(undefined_name)
            if not undefined_names:
                marked_star_import_line_numbers = frozenset()
    else:
        marked_star_import_line_numbers = frozenset()

    if remove_unused_variables:
        marked_variable_line_numbers = frozenset(
            unused_variable_line_numbers(messages))
    else:
        marked_variable_line_numbers = frozenset()

    if remove_duplicate_keys:
        marked_key_line_numbers = frozenset(
            duplicate_key_line_numbers(messages, source))
    else:
        marked_key_line_numbers = frozenset()

    line_messages = get_messages_by_line(messages)

    sio = io.StringIO(source)
    previous_line = ''
    result = None
    for line_number, line in enumerate(sio.readlines(), start=1):
        if isinstance(result, PendingFix):
            result = result(line)
        elif '#' in line:
            result = line
        elif line_number in marked_import_line_numbers:
            result = filter_unused_import(
                line,
                unused_module=marked_unused_module[line_number],
                remove_all_unused_imports=remove_all_unused_imports,
                imports=imports,
                previous_line=previous_line)
        elif line_number in marked_variable_line_numbers:
            result = filter_unused_variable(line)
        elif line_number in marked_key_line_numbers:
            result = filter_duplicate_key(line, line_messages[line_number],
                                          line_number, marked_key_line_numbers,
                                          source)
        elif line_number in marked_star_import_line_numbers:
            result = filter_star_import(line, undefined_names)
        else:
            result = line

        if not isinstance(result, PendingFix):
            yield result

        previous_line = line


def get_messages_by_line(messages):
    """Return dictionary that maps line number to message."""
    line_messages = {}
    for message in messages:
        line_messages[message.lineno] = message
    return line_messages


def filter_star_import(line, marked_star_import_undefined_name):
    """Return line with the star import expanded."""
    undefined_name = sorted(set(marked_star_import_undefined_name))
    return re.sub(r'\*', ', '.join(undefined_name), line)


def filter_unused_import(line, unused_module, remove_all_unused_imports,
                         imports, previous_line=''):
    """Return line if used, otherwise return None."""
    # Ignore doctests.
    if line.lstrip().startswith('>'):
        return line

    if multiline_import(line, previous_line):
        filt = FilterMultilineImport(line, unused_module,
                                     remove_all_unused_imports,
                                     imports, previous_line)
        return filt()

    is_from_import = line.lstrip().startswith('from')

    if ',' in line and not is_from_import:
        return break_up_import(line)

    package = extract_package_name(line)
    if not remove_all_unused_imports and package not in imports:
        return line

    if ',' in line:
        assert is_from_import
        return filter_from_import(line, unused_module)
    else:
        # We need to replace import with "pass" in case the import is the
        # only line inside a block. For example,
        # "if True:\n    import os". In such cases, if the import is
        # removed, the block will be left hanging with no body.
        return (get_indentation(line) +
                'pass' +
                get_line_ending(line))


def filter_unused_variable(line, previous_line=''):
    """Return line if used, otherwise return None."""
    if re.match(EXCEPT_REGEX, line):
        return re.sub(r' as \w+:$', ':', line, count=1)
    elif multiline_statement(line, previous_line):
        return line
    elif line.count('=') == 1:
        split_line = line.split('=')
        assert len(split_line) == 2
        value = split_line[1].lstrip()
        if ',' in split_line[0]:
            return line

        if is_literal_or_name(value):
            # Rather than removing the line, replace with it "pass" to avoid
            # a possible hanging block with no body.
            value = 'pass' + get_line_ending(line)

        return get_indentation(line) + value
    else:
        return line


def filter_duplicate_key(line, message, line_number, marked_line_numbers,
                         source, previous_line=''):
    """Return '' if first occurrence of the key otherwise return `line`."""
    if marked_line_numbers and line_number == sorted(marked_line_numbers)[0]:
        return ''

    return line


def dict_entry_has_key(line, key):
    """Return True if `line` is a dict entry that uses `key`.

    Return False for multiline cases where the line should not be removed by
    itself.

    """
    if '#' in line:
        return False

    result = re.match(r'\s*(.*)\s*:\s*(.*),\s*$', line)
    if not result:
        return False

    try:
        candidate_key = ast.literal_eval(result.group(1))
    except (SyntaxError, ValueError):
        return False

    if multiline_statement(result.group(2)):
        return False

    return candidate_key == key


def is_literal_or_name(value):
    """Return True if value is a literal or a name."""
    try:
        ast.literal_eval(value)
        return True
    except (SyntaxError, ValueError):
        pass

    if value.strip() in ['dict()', 'list()', 'set()']:
        return True

    # Support removal of variables on the right side. But make sure
    # there are no dots, which could mean an access of a property.
    return re.match(r'^\w+\s*$', value)


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
                token_type in ATOMS and
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
    except (SyntaxError, tokenize.TokenError):
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
        return ''


def get_line_ending(line):
    """Return line ending."""
    non_whitespace_index = len(line.rstrip()) - len(line)
    if not non_whitespace_index:
        return ''
    else:
        return line[non_whitespace_index:]


def fix_code(source, additional_imports=None, expand_star_imports=False,
             remove_all_unused_imports=False, remove_duplicate_keys=False,
             remove_unused_variables=False, ignore_init_module_imports=False):
    """Return code with all filtering run on it."""
    if not source:
        return source

    # pyflakes does not handle "nonlocal" correctly.
    if 'nonlocal' in source:
        remove_unused_variables = False

    filtered_source = None
    while True:
        filtered_source = ''.join(
            filter_useless_pass(''.join(
                filter_code(
                    source,
                    additional_imports=additional_imports,
                    expand_star_imports=expand_star_imports,
                    remove_all_unused_imports=remove_all_unused_imports,
                    remove_duplicate_keys=remove_duplicate_keys,
                    remove_unused_variables=remove_unused_variables,
                    ignore_init_module_imports=ignore_init_module_imports,
                ))))

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

    isInitFile = os.path.basename(filename) == '__init__.py'

    if args.ignore_init_module_imports and isInitFile:
        ignore_init_module_imports = True
    else:
        ignore_init_module_imports = False

    filtered_source = fix_code(
        source,
        additional_imports=args.imports.split(',') if args.imports else None,
        expand_star_imports=args.expand_star_imports,
        remove_all_unused_imports=args.remove_all_unused_imports,
        remove_duplicate_keys=args.remove_duplicate_keys,
        remove_unused_variables=args.remove_unused_variables,
        ignore_init_module_imports=ignore_init_module_imports,
    )

    if original_source != filtered_source:
        if args.check:
            standard_out.write(
                '{filename}: Unused imports/variables detected'.format(
                    filename=filename))
            sys.exit(1)
        if args.in_place:
            with open_with_encoding(filename, mode='w',
                                    encoding=encoding) as output_file:
                output_file.write(filtered_source)
        else:
            diff = get_diff_text(
                io.StringIO(original_source).readlines(),
                io.StringIO(filtered_source).readlines(),
                filename)
            standard_out.write(''.join(diff))
    else:
        if args.check:
            standard_out.write('No issues detected!\n')


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


def is_exclude_file(filename, exclude):
    """Return True if file matches exclude pattern."""
    base_name = os.path.basename(filename)

    if base_name.startswith('.'):
        return True

    for pattern in exclude:
        if fnmatch.fnmatch(base_name, pattern):
            return True
        if fnmatch.fnmatch(filename, pattern):
            return True
    return False


def match_file(filename, exclude):
    """Return True if file is okay for modifying/recursing."""
    if is_exclude_file(filename, exclude):
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
            if not is_exclude_file(name, exclude):
                yield name


def _main(argv, standard_out, standard_error):
    """Return exit status.

    0 means no error.
    """
    import argparse
    parser = argparse.ArgumentParser(description=__doc__, prog='autoflake')
    parser.add_argument('-c', '--check', action='store_true',
                        help='return error code if changes are needed')
    parser.add_argument('-i', '--in-place', action='store_true',
                        help='make changes to files instead of printing diffs')
    parser.add_argument('-r', '--recursive', action='store_true',
                        help='drill down directories recursively')
    parser.add_argument('--exclude', metavar='globs',
                        help='exclude file/directory names that match these '
                             'comma-separated globs')
    parser.add_argument('--imports',
                        help='by default, only unused standard library '
                             'imports are removed; specify a comma-separated '
                             'list of additional modules/packages')
    parser.add_argument('--expand-star-imports', action='store_true',
                        help='expand wildcard star imports with undefined '
                             'names; this only triggers if there is only '
                             'one star import in the file; this is skipped if '
                             'there are any uses of `__all__` or `del` in the '
                             'file')
    parser.add_argument('--remove-all-unused-imports', action='store_true',
                        help='remove all unused imports (not just those from '
                             'the standard library)')
    parser.add_argument('--ignore-init-module-imports', action='store_true',
                        help='exclude __init__.py when removing unused '
                             'imports')
    parser.add_argument('--remove-duplicate-keys', action='store_true',
                        help='remove all duplicate keys in objects')
    parser.add_argument('--remove-unused-variables', action='store_true',
                        help='remove unused variables')
    parser.add_argument('--version', action='version',
                        version='%(prog)s ' + __version__)
    parser.add_argument('files', nargs='+', help='files to format')

    args = parser.parse_args(argv[1:])

    if args.remove_all_unused_imports and args.imports:
        print('Using both --remove-all and --imports is redundant',
              file=standard_error)
        return 1

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
