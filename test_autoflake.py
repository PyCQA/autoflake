#!/usr/bin/env python
# coding: utf-8

"""Test suite for autoflake."""

from __future__ import unicode_literals

import contextlib
import io
import tempfile
import unittest

import autoflake


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

    def test_filter_unused_variables(self):
        self.assertEqual('foo()',
                         autoflake.filter_unused_variable('x = foo()'))

        self.assertEqual('    foo()',
                         autoflake.filter_unused_variable('    x = foo()'))

    def test_filter_unused_variables_with_literal_or_name(self):
        self.assertEqual('pass',
                         autoflake.filter_unused_variable('x = 1'))

        self.assertEqual('pass',
                         autoflake.filter_unused_variable('x = y'))

    def test_filter_unused_variables_should_ignore_multiline(self):
        self.assertEqual('x = foo()\\',
                         autoflake.filter_unused_variable('x = foo()\\'))

    def test_filter_unused_variables_should_multiple_assignments(self):
        self.assertEqual('x = y = foo()',
                         autoflake.filter_unused_variable('x = y = foo()'))

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

    def test_multiline_statement(self):
        self.assertFalse(autoflake.multiline_statement('x = foo()'))
        self.assertFalse(autoflake.multiline_statement('x = 1;'))

        self.assertTrue(autoflake.multiline_statement('import os, \\'))
        self.assertTrue(autoflake.multiline_statement('foo('))
        self.assertTrue(autoflake.multiline_statement('1',
                                                      previous_line='x = \\'))

    def test_break_up_import(self):
        self.assertEqual(
            'import abc\nimport subprocess\nimport math\n',
            autoflake.break_up_import('import abc, subprocess, math\n'))

    def test_break_up_import_with_indentation(self):
        self.assertEqual(
            '    import abc\n    import subprocess\n    import math\n',
            autoflake.break_up_import('    import abc, subprocess, math\n'))

    def test_break_up_import_with_from(self):
        self.assertEqual(
            """\
    from foo import abc
    from foo import subprocess
    from foo import math
""",
            autoflake.break_up_import(
                '    from foo import abc, subprocess, math\n'))

    def test_break_up_import_should_do_nothing_on_no_line_ending(self):
        self.assertEqual(
            'import abc, subprocess, math',
            autoflake.break_up_import('import abc, subprocess, math'))

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

    def test_fix_code_with_empty_string(self):
        self.assertEqual(
            '',
            autoflake.fix_code(''))

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
        self.assertFalse(autoflake.check('print("∑"'))

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
\ No newline at end of file
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
            autoflake.main(argv=['my_fake_program', filename],
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
        autoflake.main(argv=['my_fake_program', 'nonexistent_file'],
                       standard_out=output_file,
                       standard_error=output_file)
        self.assertIn('no such file', output_file.getvalue().lower())

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
            autoflake.main(argv=['my_fake_program', '--in-place', filename],
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
            autoflake.main(argv=['my_fake_program', '--in-place', filename],
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
            autoflake.main(argv=['my_fake_program', '--in-place', filename],
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
        autoflake.main(argv=['my_fake_program', '--in-place', '.fake'],
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
                    autoflake.main(argv=['my_fake_program',
                                         '--recursive',
                                         directory],
                                   standard_out=output_file,
                                   standard_error=None)
                    self.assertEqual(
                        '',
                        output_file.getvalue().strip())

    def test_redundant_options(self):
        output_file = io.StringIO()
        autoflake.main(argv=['my_fake_program',
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
            import subprocess
            process = subprocess.Popen(['./autoflake',
                                        '--imports=fake_foo,fake_bar',
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
""", '\n'.join(process.communicate()[0].decode('utf-8').split('\n')[3:]))

    def test_end_to_end_with_remove_all_unused_imports(self):
        with temporary_file("""\
import fake_fake, fake_foo, fake_bar, fake_zoo
import re, os
x = os.sep
print(x)
""") as filename:
            import subprocess
            process = subprocess.Popen(['./autoflake',
                                        '--remove-all',
                                        filename],
                                       stdout=subprocess.PIPE)
            self.assertEqual("""\
-import fake_fake, fake_foo, fake_bar, fake_zoo
-import re, os
+import os
 x = os.sep
 print(x)
""", '\n'.join(process.communicate()[0].decode('utf-8').split('\n')[3:]))

    def test_end_to_end_with_error(self):
        with temporary_file("""\
import fake_fake, fake_foo, fake_bar, fake_zoo
import re, os
x = os.sep
print(x)
""") as filename:
            import subprocess
            process = subprocess.Popen(['./autoflake',
                                        '--imports=fake_foo,fake_bar',
                                        '--remove-all',
                                        filename],
                                       stderr=subprocess.PIPE)
            self.assertIn(
                'redundant',
                process.communicate()[1].decode('utf-8'))


@contextlib.contextmanager
def temporary_file(contents, directory='.', prefix=''):
    """Write contents to temporary file and yield it."""
    f = tempfile.NamedTemporaryFile(suffix='.py', prefix=prefix,
                                    delete=False, dir=directory)
    try:
        f.write(contents.encode('utf8'))
        f.close()
        yield f.name
    finally:
        import os
        os.remove(f.name)


@contextlib.contextmanager
def temporary_directory(directory='.', prefix=''):
    """Create temporary directory and yield its path."""
    temp_directory = tempfile.mkdtemp(prefix=prefix, dir=directory)
    try:
        yield temp_directory
    finally:
        import shutil
        shutil.rmtree(temp_directory)


class StubFile(object):

    """Fake file that ignores everything."""

    def write(*_):
        """Ignore."""


if __name__ == '__main__':
    unittest.main()
