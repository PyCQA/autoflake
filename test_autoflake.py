#!/usr/bin/env python
# coding: utf-8

"""Test suite for autoflake."""

from __future__ import unicode_literals

import contextlib
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

import autoflake


ROOT_DIRECTORY = os.path.abspath(os.path.dirname(__file__))


if (
    'AUTOFLAKE_COVERAGE' in os.environ and
    int(os.environ['AUTOFLAKE_COVERAGE'])
):
    AUTOFLAKE_COMMAND = ['coverage', 'run', '--branch', '--parallel',
                         '--omit=*/distutils/*,*/site-packages/*',
                         os.path.join(ROOT_DIRECTORY, 'autoflake.py')]
else:
    # We need to specify the executable to make sure the correct Python
    # interpreter gets used.
    AUTOFLAKE_COMMAND = [sys.executable,
                         os.path.join(
                             ROOT_DIRECTORY,
                             'autoflake.py')]  # pragma: no cover


class UnitTests(unittest.TestCase):

    """Unit tests."""

    def test_imports(self):
        self.assertGreater(len(autoflake.SAFE_IMPORTS), 0)

    def test_unused_import_line_numbers(self):
        self.assertEqual(
            [1],
            list(autoflake.unused_import_line_numbers(
                autoflake.check('import os\n'))))

    def test_unused_import_line_numbers_with_from(self):
        self.assertEqual(
            [1],
            list(autoflake.unused_import_line_numbers(
                autoflake.check('from os import path\n'))))

    def test_unused_import_line_numbers_with_dot(self):
        self.assertEqual(
            [1],
            list(autoflake.unused_import_line_numbers(
                autoflake.check('import os.path\n'))))

    def test_extract_package_name(self):
        self.assertEqual('os', autoflake.extract_package_name('import os'))
        self.assertEqual(
            'os', autoflake.extract_package_name('from os import path'))
        self.assertEqual(
            'os', autoflake.extract_package_name('import os.path'))

    def test_extract_package_name_should_ignore_doctest_for_now(self):
        self.assertFalse(autoflake.extract_package_name('>>> import os'))

    def test_standard_package_names(self):
        self.assertIn('os', list(autoflake.standard_package_names()))
        self.assertIn('subprocess', list(autoflake.standard_package_names()))
        self.assertIn('urllib', list(autoflake.standard_package_names()))

        self.assertNotIn('autoflake', list(autoflake.standard_package_names()))
        self.assertNotIn('pep8', list(autoflake.standard_package_names()))

    def test_get_line_ending(self):
        self.assertEqual('\n', autoflake.get_line_ending('\n'))
        self.assertEqual('\n', autoflake.get_line_ending('abc\n'))
        self.assertEqual('\t  \t\n', autoflake.get_line_ending('abc\t  \t\n'))

        self.assertEqual('', autoflake.get_line_ending('abc'))
        self.assertEqual('', autoflake.get_line_ending(''))

    def test_get_indentation(self):
        self.assertEqual('', autoflake.get_indentation(''))
        self.assertEqual('    ', autoflake.get_indentation('    abc'))
        self.assertEqual('    ', autoflake.get_indentation('    abc  \n\t'))
        self.assertEqual('\t', autoflake.get_indentation('\tabc  \n\t'))
        self.assertEqual(' \t ', autoflake.get_indentation(' \t abc  \n\t'))
        self.assertEqual('', autoflake.get_indentation('    '))

    def test_filter_star_import(self):
        self.assertEqual(
            'from math import cos',
            autoflake.filter_star_import('from math import *',
                                         ['cos']))

        self.assertEqual(
            'from math import cos, sin',
            autoflake.filter_star_import('from math import *',
                                         ['sin', 'cos']))

    def test_filter_duplicate_key_multiple_lines(self):
        class mock_line_message(object):
            message_args = ('a',)

        source = """\
a = {
    'a': 1,
    'a': 2,
    'b': 1,
    'a': 3,
    'c': 5,
}
"""

        self.assertEqual('',
                         autoflake.filter_duplicate_key(
                             "    'a': 1,",
                             mock_line_message,
                             2,
                             [2, 3, 5],
                             source))

        self.assertEqual('',
                         autoflake.filter_duplicate_key(
                             "    'a': 2,",
                             mock_line_message,
                             3,
                             [2, 3, 5],
                             source))

        self.assertEqual("    'a': 3",
                         autoflake.filter_duplicate_key(
                             "    'a': 3",
                             mock_line_message,
                             5,
                             [2, 3, 5],
                             source))

    def test_filter_duplicate_key_tuple(self):
        class mock_line_message(object):
            message_args = ((0, 1),)

        source = """\
a = {
    (0,1): 1,
    (0, 1): 2,
    (1,2): 1,
    'a': 3,
    (0, 1): 5,
}
"""

        self.assertEqual('',
                         autoflake.filter_duplicate_key(
                             '    (0,1): 1,',
                             mock_line_message,
                             2,
                             [2, 3, 6],
                             source))

        self.assertEqual('',
                         autoflake.filter_duplicate_key(
                             '    (0, 1): 2,',
                             mock_line_message,
                             3,
                             [2, 3, 6],
                             source))

        self.assertEqual('    (0, 1): 5,',
                         autoflake.filter_duplicate_key(
                             '    (0, 1): 5,',
                             mock_line_message,
                             6,
                             [2, 3, 6],
                             source))

    def test_filter_unused_variable(self):
        self.assertEqual('foo()',
                         autoflake.filter_unused_variable('x = foo()'))

        self.assertEqual('    foo()',
                         autoflake.filter_unused_variable('    x = foo()'))

    def test_filter_unused_variable_with_literal_or_name(self):
        self.assertEqual('pass',
                         autoflake.filter_unused_variable('x = 1'))

        self.assertEqual('pass',
                         autoflake.filter_unused_variable('x = y'))

        self.assertEqual('pass',
                         autoflake.filter_unused_variable('x = {}'))

    def test_filter_unused_variable_with_basic_data_structures(self):
        self.assertEqual('pass',
                         autoflake.filter_unused_variable('x = dict()'))

        self.assertEqual('pass',
                         autoflake.filter_unused_variable('x = list()'))

        self.assertEqual('pass',
                         autoflake.filter_unused_variable('x = set()'))

    def test_filter_unused_variable_should_ignore_multiline(self):
        self.assertEqual('x = foo()\\',
                         autoflake.filter_unused_variable('x = foo()\\'))

    def test_filter_unused_variable_should_multiple_assignments(self):
        self.assertEqual('x = y = foo()',
                         autoflake.filter_unused_variable('x = y = foo()'))

    def test_filter_unused_variable_with_exception(self):
        self.assertEqual(
            'except Exception:',
            autoflake.filter_unused_variable('except Exception as exception:'))

        self.assertEqual(
            'except (ImportError, ValueError):',
            autoflake.filter_unused_variable(
                'except (ImportError, ValueError) as foo:'))

    def test_filter_code(self):
        self.assertEqual(
            """\
import os
pass
os.foo()
""",
            ''.join(autoflake.filter_code("""\
import os
import re
os.foo()
""")))

    def test_filter_code_with_indented_import(self):
        self.assertEqual(
            """\
import os
if True:
    pass
os.foo()
""",
            ''.join(autoflake.filter_code("""\
import os
if True:
    import re
os.foo()
""")))

    def test_filter_code_with_from(self):
        self.assertEqual(
            """\
pass
x = 1
""",
            ''.join(autoflake.filter_code("""\
from os import path
x = 1
""")))

    def test_filter_code_with_not_from(self):
        self.assertEqual(
            """\
pass
x = 1
""",
            ''.join(autoflake.filter_code("""\
import frommer
x = 1
""",
                                          remove_all_unused_imports=True)))

    def test_filter_code_with_used_from(self):
        self.assertEqual(
            """\
import frommer
print(frommer)
""",
            ''.join(autoflake.filter_code("""\
import frommer
print(frommer)
""",
                                          remove_all_unused_imports=True)))

    def test_filter_code_with_ambiguous_from(self):
        self.assertEqual(
            """\
pass
""",
            ''.join(autoflake.filter_code("""\
from frommer import abc, frommer, xyz
""",
                                          remove_all_unused_imports=True)))

    def test_filter_code_should_avoid_inline_except(self):
        line = """\
try: from zap import foo
except: from zap import bar
"""
        self.assertEqual(
            line,
            ''.join(autoflake.filter_code(line,
                                          remove_all_unused_imports=True)))

    def test_filter_code_should_avoid_escaped_newlines(self):
        line = """\
try:\\
from zap import foo
except:\\
from zap import bar
"""
        self.assertEqual(
            line,
            ''.join(autoflake.filter_code(line,
                                          remove_all_unused_imports=True)))

    def test_filter_code_with_remove_all_unused_imports(self):
        self.assertEqual(
            """\
pass
pass
x = 1
""",
            ''.join(autoflake.filter_code("""\
import foo
import zap
x = 1
""", remove_all_unused_imports=True)))

    def test_filter_code_with_additional_imports(self):
        self.assertEqual(
            """\
pass
import zap
x = 1
""",
            ''.join(autoflake.filter_code("""\
import foo
import zap
x = 1
""", additional_imports=['foo', 'bar'])))

    def test_filter_code_should_ignore_imports_with_inline_comment(self):
        self.assertEqual(
            """\
from os import path  # foo
pass
from fake_foo import z  # foo, foo, zap
x = 1
""",
            ''.join(autoflake.filter_code("""\
from os import path  # foo
from os import path
from fake_foo import z  # foo, foo, zap
x = 1
""")))

    def test_filter_code_should_respect_noqa(self):
        self.assertEqual(
            """\
pass
import re  # noqa
from subprocess import Popen  # NOQA
x = 1
""",
            ''.join(autoflake.filter_code("""\
from os import path
import re  # noqa
from subprocess import Popen  # NOQA
x = 1
""")))

    def test_filter_code_expand_star_imports(self):
        self.assertEqual(
            """\
from math import sin
sin(1)
""",
            ''.join(autoflake.filter_code("""\
from math import *
sin(1)
""", expand_star_imports=True)))

        self.assertEqual(
            """\
from math import cos, sin
sin(1)
cos(1)
""",
            ''.join(autoflake.filter_code("""\
from math import *
sin(1)
cos(1)
""", expand_star_imports=True)))

    def test_filter_code_ignore_multiple_star_import(self):
        self.assertEqual(
            """\
from math import *
from re import *
sin(1)
cos(1)
""",
            ''.join(autoflake.filter_code("""\
from math import *
from re import *
sin(1)
cos(1)
""", expand_star_imports=True)))

    def test_filter_code_with_duplicate_key(self):
        self.assertEqual(
            """\
a = {
  (0,1): 3,
}
print(a)
""",
            ''.join(autoflake.filter_code("""\
a = {
  (0,1): 1,
  (0, 1): 'two',
  (0,1): 3,
}
print(a)
""", remove_duplicate_keys=True)))

    def test_filter_code_with_special_re_symbols_in_key(self):
        self.assertEqual(
            """\
a = {
  '????': 2,
}
print(a)
""",
            ''.join(autoflake.filter_code("""\
a = {
  '????': 3,
  '????': 2,
}
print(a)
""", remove_duplicate_keys=True)))

    def test_filter_code_should_ignore_complex_case_of_duplicate_key(self):
        """We only handle simple cases."""
        code = """\
a = {(0,1): 1, (0, 1): 'two',
  (0,1): 3,
}
print(a)
"""

        self.assertEqual(
            code,
            ''.join(autoflake.filter_code(code,
                                          remove_duplicate_keys=True)))

    def test_multiline_import(self):
        self.assertTrue(autoflake.multiline_import(r"""\
import os, \
    math, subprocess
"""))

        self.assertFalse(autoflake.multiline_import("""\
import os, math, subprocess
"""))

        self.assertTrue(autoflake.multiline_import("""\
import os, math, subprocess
""", previous_line='if: \\\n'))

        self.assertTrue(
            autoflake.multiline_import('from os import (path, sep)'))

    def test_multiline_statement(self):
        self.assertFalse(autoflake.multiline_statement('x = foo()'))

        self.assertTrue(autoflake.multiline_statement('x = 1;'))
        self.assertTrue(autoflake.multiline_statement('import os, \\'))
        self.assertTrue(autoflake.multiline_statement('foo('))
        self.assertTrue(autoflake.multiline_statement('1',
                                                      previous_line='x = \\'))

    def test_break_up_import(self):
        self.assertEqual(
            'import abc\nimport math\nimport subprocess\n',
            autoflake.break_up_import('import abc, subprocess, math\n'))

    def test_break_up_import_with_indentation(self):
        self.assertEqual(
            '    import abc\n    import math\n    import subprocess\n',
            autoflake.break_up_import('    import abc, subprocess, math\n'))

    def test_break_up_import_should_do_nothing_on_no_line_ending(self):
        self.assertEqual(
            'import abc, subprocess, math',
            autoflake.break_up_import('import abc, subprocess, math'))

    def test_filter_from_import_no_remove(self):
        self.assertEqual(
            """\
    from foo import abc, math, subprocess\n""",
            autoflake.filter_from_import(
                '    from foo import abc, subprocess, math\n',
                unused_module=[]))

    def test_filter_from_import_remove_module(self):
        self.assertEqual(
            """\
    from foo import math, subprocess\n""",
            autoflake.filter_from_import(
                '    from foo import abc, subprocess, math\n',
                unused_module=['foo.abc']))

    def test_filter_from_import_remove_all(self):
        self.assertEqual(
            '    pass\n',
            autoflake.filter_from_import(
                '    from foo import abc, subprocess, math\n',
                unused_module=['foo.abc', 'foo.subprocess',
                               'foo.math']))

    def test_filter_code_should_ignore_multiline_imports(self):
        self.assertEqual(
            r"""\
import os
pass
import os, \
    math, subprocess
os.foo()
""",
            ''.join(autoflake.filter_code(r"""\
import os
import re
import os, \
    math, subprocess
os.foo()
""")))

    def test_filter_code_should_ignore_semicolons(self):
        self.assertEqual(
            r"""\
import os
pass
import os; import math, subprocess
os.foo()
""",
            ''.join(autoflake.filter_code(r"""\
import os
import re
import os; import math, subprocess
os.foo()
""")))

    def test_filter_code_should_ignore_non_standard_library(self):
        self.assertEqual(
            """\
import os
import my_own_module
pass
from my_package import another_module
from my_package import subprocess
from my_blah.my_blah_blah import blah
os.foo()
""",
            ''.join(autoflake.filter_code("""\
import os
import my_own_module
import re
from my_package import another_module
from my_package import subprocess
from my_blah.my_blah_blah import blah
os.foo()
""")))

    def test_filter_code_should_ignore_unsafe_imports(self):
        self.assertEqual(
            """\
import rlcompleter
pass
pass
pass
print(1)
""",
            ''.join(autoflake.filter_code("""\
import rlcompleter
import sys
import io
import os
print(1)
""")))

    def test_filter_code_should_ignore_docstring(self):
        line = """
def foo():
    '''
    >>> import math
    '''
"""
        self.assertEqual(line, ''.join(autoflake.filter_code(line)))

    def test_fix_code(self):
        self.assertEqual(
            """\
import os
import math
from sys import version
os.foo()
math.pi
x = version
""",
            autoflake.fix_code("""\
import os
import re
import abc, math, subprocess
from sys import exit, version
os.foo()
math.pi
x = version
"""))

    def test_fix_code_with_from_and_as(self):
        self.assertEqual(
            """\
from collections import namedtuple as xyz
xyz
""",
            autoflake.fix_code("""\
from collections import defaultdict, namedtuple as xyz
xyz
"""))

        self.assertEqual(
            """\
from collections import namedtuple as xyz
xyz
""",
            autoflake.fix_code("""\
from collections import defaultdict as abc, namedtuple as xyz
xyz
"""))

        self.assertEqual(
            """\
from collections import namedtuple
namedtuple
""",
            autoflake.fix_code("""\
from collections import defaultdict as abc, namedtuple
namedtuple
"""))

        self.assertEqual(
            """\
""",
            autoflake.fix_code("""\
from collections import defaultdict as abc, namedtuple as xyz
"""))

    def test_fix_code_with_from_with_and_without_remove_all(self):
        code = """\
from x import a as b, c as d
"""

        self.assertEqual(
            """\
""",
            autoflake.fix_code(code, remove_all_unused_imports=True))

        self.assertEqual(
            code,
            autoflake.fix_code(code, remove_all_unused_imports=False))

    def test_fix_code_with_from_and_depth_module(self):
        self.assertEqual(
            """\
from distutils.version import StrictVersion
StrictVersion('1.0.0')
""",
            autoflake.fix_code("""\
from distutils.version import LooseVersion, StrictVersion
StrictVersion('1.0.0')
"""))

        self.assertEqual(
            """\
from distutils.version import StrictVersion as version
version('1.0.0')
""",
            autoflake.fix_code("""\
from distutils.version import LooseVersion, StrictVersion as version
version('1.0.0')
"""))

    def test_fix_code_with_indented_from(self):
        self.assertEqual(
            """\
def z():
    from ctypes import POINTER, byref
    POINTER, byref
    """,
            autoflake.fix_code("""\
def z():
    from ctypes import c_short, c_uint, c_int, c_long, pointer, POINTER, byref
    POINTER, byref
    """))

        self.assertEqual(
            """\
def z():
    pass
""",
            autoflake.fix_code("""\
def z():
    from ctypes import c_short, c_uint, c_int, c_long, pointer, POINTER, byref
"""))

    def test_fix_code_with_empty_string(self):
        self.assertEqual(
            '',
            autoflake.fix_code(''))

    def test_fix_code_with_from_and_as_and_escaped_newline(self):
        """Make sure stuff after escaped newline is not lost."""
        result = autoflake.fix_code("""\
from collections import defaultdict, namedtuple \\
    as xyz
xyz
""")
        # We currently leave lines with escaped newlines as is. But in the
        # future this we may parse them and remove unused import accordingly.
        # For now, we'll work around it here.
        result = re.sub(r' *\\\n *as ', ' as ', result)

        self.assertEqual(
            """\
from collections import namedtuple as xyz
xyz
""",
            autoflake.fix_code(result))

    def test_fix_code_with_unused_variables(self):
        self.assertEqual(
            """\
def main():
    y = 11
    print(y)
""",
            autoflake.fix_code("""\
def main():
    x = 10
    y = 11
    print(y)
""",
                               remove_unused_variables=True))

    def test_fix_code_with_unused_variables_should_skip_nonlocal(self):
        """pyflakes does not handle nonlocal correctly."""
        code = """\
def bar():
    x = 1

    def foo():
        nonlocal x
        x = 2
"""
        self.assertEqual(
            code,
            autoflake.fix_code(code,
                               remove_unused_variables=True))

    def test_detect_encoding_with_bad_encoding(self):
        with temporary_file('# -*- coding: blah -*-\n') as filename:
            self.assertEqual('latin-1',
                             autoflake.detect_encoding(filename))

    def test_fix_code_with_comma_on_right(self):
        """pyflakes does not handle nonlocal correctly."""
        self.assertEqual(
            """\
def main():
    pass
""",
            autoflake.fix_code("""\
def main():
    x = (1, 2, 3)
""",
                               remove_unused_variables=True))

    def test_fix_code_with_unused_variables_should_skip_multiple(self):
        code = """\
def main():
    (x, y, z) = (1, 2, 3)
    print(z)
"""
        self.assertEqual(
            code,
            autoflake.fix_code(code,
                               remove_unused_variables=True))

    def test_fix_code_should_handle_pyflakes_recursion_error_gracefully(self):
        code = 'x = [{}]'.format('+'.join(['abc' for _ in range(2000)]))
        self.assertEqual(
            code,
            autoflake.fix_code(code))

    def test_useless_pass_line_numbers(self):
        self.assertEqual(
            [1],
            list(autoflake.useless_pass_line_numbers(
                'pass\n')))

        self.assertEqual(
            [],
            list(autoflake.useless_pass_line_numbers(
                'if True:\n    pass\n')))

    def test_useless_pass_line_numbers_with_escaped_newline(self):
        self.assertEqual(
            [],
            list(autoflake.useless_pass_line_numbers(
                'if True:\\\n    pass\n')))

    def test_useless_pass_line_numbers_with_more_complex(self):
        self.assertEqual(
            [6],
            list(autoflake.useless_pass_line_numbers(
                """\
if True:
    pass
else:
    True
    x = 1
    pass
""")))

    def test_filter_useless_pass(self):
        self.assertEqual(
            """\
if True:
    pass
else:
    True
    x = 1
""",
            ''.join(autoflake.filter_useless_pass(
                """\
if True:
    pass
else:
    True
    x = 1
    pass
""")))

    def test_filter_useless_pass_with_syntax_error(self):
        source = """\
if True:
if True:
            if True:
    if True:

if True:
    pass
else:
    True
    pass
    pass
    x = 1
"""

        self.assertEqual(
            source,
            ''.join(autoflake.filter_useless_pass(source)))

    def test_filter_useless_pass_more_complex(self):
        self.assertEqual(
            """\
if True:
    pass
else:
    def foo():
        pass
        # abc
    def bar():
        # abc
        pass
    def blah():
        123
        pass  # Nope.
    True
    x = 1
""",
            ''.join(autoflake.filter_useless_pass(
                """\
if True:
    pass
else:
    def foo():
        pass
        # abc
    def bar():
        # abc
        pass
    def blah():
        123
        pass
        pass  # Nope.
        pass
    True
    x = 1
    pass
""")))

    def test_filter_useless_pass_with_try(self):
        self.assertEqual(
            """\
import os
os.foo()
try:
    pass
except ImportError:
    pass
""",
            ''.join(autoflake.filter_useless_pass(
                """\
import os
os.foo()
try:
    pass
    pass
except ImportError:
    pass
""")))

    def test_filter_useless_pass_leading_pass(self):
        self.assertEqual(
            """\
if True:
    pass
else:
    True
    x = 1
""",
            ''.join(autoflake.filter_useless_pass(
                """\
if True:
    pass
    pass
    pass
    pass
else:
    pass
    True
    x = 1
    pass
""")))

    def test_filter_useless_pass_leading_pass_with_number(self):
        self.assertEqual(
            """\
def func11():
    0, 11 / 2
    return 1
""",
            ''.join(autoflake.filter_useless_pass(
                """\
def func11():
    pass
    0, 11 / 2
    return 1
""")))

    def test_filter_useless_pass_leading_pass_with_string(self):
        self.assertEqual(
            """\
def func11():
    'hello'
    return 1
""",
            ''.join(autoflake.filter_useless_pass(
                """\
def func11():
    pass
    'hello'
    return 1
""")))

    def test_check(self):
        self.assertTrue(autoflake.check('import os'))

    def test_check_with_bad_syntax(self):
        self.assertFalse(autoflake.check('foo('))

    def test_check_with_unicode(self):
        self.assertFalse(autoflake.check('print("∑")'))

        self.assertTrue(autoflake.check('import os  # ∑'))

    def test_get_diff_text(self):
        # We ignore the first two lines since it differs on Python 2.6.
        self.assertEqual(
            """\
-foo
+bar
""",
            '\n'.join(autoflake.get_diff_text(['foo\n'],
                                              ['bar\n'],
                                              '').split('\n')[3:]))

    def test_get_diff_text_without_newline(self):
        # We ignore the first two lines since it differs on Python 2.6.
        self.assertEqual(
            """\
-foo
\\ No newline at end of file
+foo
""",
            '\n'.join(autoflake.get_diff_text(['foo'],
                                              ['foo\n'],
                                              '').split('\n')[3:]))

    def test_is_literal_or_name(self):
        self.assertTrue(autoflake.is_literal_or_name('123'))
        self.assertTrue(autoflake.is_literal_or_name('[1, 2, 3]'))
        self.assertTrue(autoflake.is_literal_or_name('xyz'))

        self.assertFalse(autoflake.is_literal_or_name('xyz.prop'))
        self.assertFalse(autoflake.is_literal_or_name(' '))
        self.assertFalse(autoflake.is_literal_or_name(' 1'))

    def test_is_python_file(self):
        self.assertTrue(autoflake.is_python_file(
            os.path.join(ROOT_DIRECTORY, 'autoflake.py')))

        with temporary_file('#!/usr/bin/env python', suffix='') as filename:
            self.assertTrue(autoflake.is_python_file(filename))

        with temporary_file('#!/usr/bin/python', suffix='') as filename:
            self.assertTrue(autoflake.is_python_file(filename))

        with temporary_file('#!/usr/bin/python3', suffix='') as filename:
            self.assertTrue(autoflake.is_python_file(filename))

        with temporary_file('#!/usr/bin/pythonic', suffix='') as filename:
            self.assertFalse(autoflake.is_python_file(filename))

        with temporary_file('###!/usr/bin/python', suffix='') as filename:
            self.assertFalse(autoflake.is_python_file(filename))

        self.assertFalse(autoflake.is_python_file(os.devnull))
        self.assertFalse(autoflake.is_python_file('/bin/bash'))

    def test_match_file(self):
        with temporary_file('', suffix='.py', prefix='.') as filename:
            self.assertFalse(autoflake.match_file(filename, exclude=[]),
                             msg=filename)

        self.assertFalse(autoflake.match_file(os.devnull, exclude=[]))

        with temporary_file('', suffix='.py', prefix='') as filename:
            self.assertTrue(autoflake.match_file(filename, exclude=[]),
                            msg=filename)

    def test_find_files(self):
        temp_directory = tempfile.mkdtemp()
        try:
            target = os.path.join(temp_directory, 'dir')
            os.mkdir(target)
            with open(os.path.join(target, 'a.py'), 'w'):
                pass

            exclude = os.path.join(target, 'ex')
            os.mkdir(exclude)
            with open(os.path.join(exclude, 'b.py'), 'w'):
                pass

            sub = os.path.join(exclude, 'sub')
            os.mkdir(sub)
            with open(os.path.join(sub, 'c.py'), 'w'):
                pass

            # FIXME: Avoid changing directory. This may interfere with parallel
            # test runs.
            cwd = os.getcwd()
            os.chdir(temp_directory)
            try:
                files = list(autoflake.find_files(
                    ['dir'], True, [os.path.join('dir', 'ex')]))
            finally:
                os.chdir(cwd)

            file_names = [os.path.basename(f) for f in files]
            self.assertIn('a.py', file_names)
            self.assertNotIn('b.py', file_names)
            self.assertNotIn('c.py', file_names)
        finally:
            shutil.rmtree(temp_directory)

    def test_exclude(self):
        temp_directory = tempfile.mkdtemp(dir='.')
        try:
            with open(os.path.join(temp_directory, 'a.py'), 'w') as output:
                output.write('import re\n')

            os.mkdir(os.path.join(temp_directory, 'd'))
            with open(os.path.join(temp_directory, 'd', 'b.py'),
                      'w') as output:
                output.write('import os\n')

            p = subprocess.Popen(
                list(AUTOFLAKE_COMMAND) +
                [temp_directory, '--recursive', '--exclude=a*'],
                stdout=subprocess.PIPE)
            result = p.communicate()[0].decode('utf-8')

            self.assertNotIn('import re', result)
            self.assertIn('import os', result)
        finally:
            shutil.rmtree(temp_directory)


class SystemTests(unittest.TestCase):

    """System tests."""

    def test_diff(self):
        with temporary_file("""\
import re
import os
import my_own_module
x = 1
""") as filename:
            output_file = io.StringIO()
            autoflake._main(argv=['my_fake_program', filename],
                            standard_out=output_file,
                            standard_error=None)
            self.assertEqual("""\
-import re
-import os
 import my_own_module
 x = 1
""", '\n'.join(output_file.getvalue().split('\n')[3:]))

    def test_diff_with_nonexistent_file(self):
        output_file = io.StringIO()
        autoflake._main(argv=['my_fake_program', 'nonexistent_file'],
                        standard_out=output_file,
                        standard_error=output_file)
        self.assertIn('no such file', output_file.getvalue().lower())

    def test_diff_with_encoding_declaration(self):
        with temporary_file("""\
# coding: iso-8859-1
import re
import os
import my_own_module
x = 1
""") as filename:
            output_file = io.StringIO()
            autoflake._main(argv=['my_fake_program', filename],
                            standard_out=output_file,
                            standard_error=None)
            self.assertEqual("""\
 # coding: iso-8859-1
-import re
-import os
 import my_own_module
 x = 1
""", '\n'.join(output_file.getvalue().split('\n')[3:]))

    def test_in_place(self):
        with temporary_file("""\
import foo
x = foo
import subprocess
x()

try:
    import os
except ImportError:
    import os
""") as filename:
            output_file = io.StringIO()
            autoflake._main(argv=['my_fake_program', '--in-place', filename],
                            standard_out=output_file,
                            standard_error=None)
            with open(filename) as f:
                self.assertEqual("""\
import foo
x = foo
x()

try:
    pass
except ImportError:
    pass
""", f.read())

    def test_in_place_with_empty_file(self):
        line = ''

        with temporary_file(line) as filename:
            output_file = io.StringIO()
            autoflake._main(argv=['my_fake_program', '--in-place', filename],
                            standard_out=output_file,
                            standard_error=None)
            with open(filename) as f:
                self.assertEqual(line, f.read())

    def test_in_place_with_with_useless_pass(self):
        with temporary_file("""\
import foo
x = foo
import subprocess
x()

try:
    pass
    import os
except ImportError:
    pass
    import os
    import sys
""") as filename:
            output_file = io.StringIO()
            autoflake._main(argv=['my_fake_program', '--in-place', filename],
                            standard_out=output_file,
                            standard_error=None)
            with open(filename) as f:
                self.assertEqual("""\
import foo
x = foo
x()

try:
    pass
except ImportError:
    pass
""", f.read())

    def test_with_missing_file(self):
        output_file = io.StringIO()
        ignore = StubFile()
        autoflake._main(argv=['my_fake_program', '--in-place', '.fake'],
                        standard_out=output_file,
                        standard_error=ignore)
        self.assertFalse(output_file.getvalue())

    def test_ignore_hidden_directories(self):
        with temporary_directory() as directory:
            with temporary_directory(prefix='.',
                                     directory=directory) as inner_directory:

                with temporary_file("""\
import re
import os
""", directory=inner_directory):

                    output_file = io.StringIO()
                    autoflake._main(argv=['my_fake_program',
                                          '--recursive',
                                          directory],
                                    standard_out=output_file,
                                    standard_error=None)
                    self.assertEqual(
                        '',
                        output_file.getvalue().strip())

    def test_redundant_options(self):
        output_file = io.StringIO()
        autoflake._main(argv=['my_fake_program',
                              '--remove-all', '--imports=blah', __file__],
                        standard_out=output_file,
                        standard_error=output_file)

        self.assertIn('redundant', output_file.getvalue())

    def test_end_to_end(self):
        with temporary_file("""\
import fake_fake, fake_foo, fake_bar, fake_zoo
import re, os
x = os.sep
print(x)
""") as filename:
            process = subprocess.Popen(AUTOFLAKE_COMMAND +
                                       ['--imports=fake_foo,fake_bar',
                                        filename],
                                       stdout=subprocess.PIPE)
            self.assertEqual("""\
-import fake_fake, fake_foo, fake_bar, fake_zoo
-import re, os
+import fake_fake
+import fake_zoo
+import os
 x = os.sep
 print(x)
""", '\n'.join(process.communicate()[0].decode().split('\n')[3:]))

    def test_end_to_end_with_remove_all_unused_imports(self):
        with temporary_file("""\
import fake_fake, fake_foo, fake_bar, fake_zoo
import re, os
x = os.sep
print(x)
""") as filename:
            process = subprocess.Popen(AUTOFLAKE_COMMAND +
                                       ['--remove-all',
                                        filename],
                                       stdout=subprocess.PIPE)
            self.assertEqual("""\
-import fake_fake, fake_foo, fake_bar, fake_zoo
-import re, os
+import os
 x = os.sep
 print(x)
""", '\n'.join(process.communicate()[0].decode().split('\n')[3:]))

    def test_end_to_end_with_remove_duplicate_keys_multiple_lines(self):
        with temporary_file("""\
a = {
    'b': 456,
    'a': 123,
    'b': 7834,
    'a': 'wow',
    'b': 456,
    'c': 'hello',
    'c': 'hello2',
    'b': 'hiya',
    "b": 'hiya',
}
print(a)
""") as filename:
            process = subprocess.Popen(AUTOFLAKE_COMMAND +
                                       ['--remove-duplicate-keys',
                                        filename],
                                       stdout=subprocess.PIPE)
            self.assertEqual("""\
 a = {
-    'b': 456,
-    'a': 123,
-    'b': 7834,
     'a': 'wow',
-    'b': 456,
-    'c': 'hello',
     'c': 'hello2',
-    'b': 'hiya',
     "b": 'hiya',
 }
 print(a)
""", '\n'.join(process.communicate()[0].decode().split('\n')[3:]))

    def test_end_to_end_with_remove_duplicate_keys_tuple(self):
        with temporary_file("""\
a = {
  (0,1): 1,
  (0, 1): 'two',
  (0,1): 3,
}
print(a)
""") as filename:
            process = subprocess.Popen(AUTOFLAKE_COMMAND +
                                       ['--remove-duplicate-keys',
                                        filename],
                                       stdout=subprocess.PIPE)
            self.assertEqual("""\
 a = {
-  (0,1): 1,
-  (0, 1): 'two',
   (0,1): 3,
 }
 print(a)
""", '\n'.join(process.communicate()[0].decode().split('\n')[3:]))

    def test_end_to_end_with_error(self):
        with temporary_file("""\
import fake_fake, fake_foo, fake_bar, fake_zoo
import re, os
x = os.sep
print(x)
""") as filename:
            process = subprocess.Popen(AUTOFLAKE_COMMAND +
                                       ['--imports=fake_foo,fake_bar',
                                        '--remove-all',
                                        filename],
                                       stderr=subprocess.PIPE)
            self.assertIn(
                'redundant',
                process.communicate()[1].decode())


@contextlib.contextmanager
def temporary_file(contents, directory='.', suffix='.py', prefix=''):
    """Write contents to temporary file and yield it."""
    f = tempfile.NamedTemporaryFile(suffix=suffix, prefix=prefix,
                                    delete=False, dir=directory)
    try:
        f.write(contents.encode())
        f.close()
        yield f.name
    finally:
        os.remove(f.name)


@contextlib.contextmanager
def temporary_directory(directory='.', prefix='tmp.'):
    """Create temporary directory and yield its path."""
    temp_directory = tempfile.mkdtemp(prefix=prefix, dir=directory)
    try:
        yield temp_directory
    finally:
        shutil.rmtree(temp_directory)


class StubFile(object):

    """Fake file that ignores everything."""

    def write(*_):
        """Ignore."""


if __name__ == '__main__':
    unittest.main()
