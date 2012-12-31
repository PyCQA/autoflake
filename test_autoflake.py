#!/usr/bin/env python

"""Test suite for autoflake."""

import contextlib
import io
import tempfile
import unittest

import autoflake


try:
    unicode
except NameError:
    unicode = str


class UnitTests(unittest.TestCase):

    """Unit tests."""

    def test_unused_import_line_numbers(self):
        self.assertEqual(
            [1],
            list(autoflake.unused_import_line_numbers(
                unicode('import os\n'))))

    def test_unused_import_line_numbers_with_from(self):
        self.assertEqual(
            [1],
            list(autoflake.unused_import_line_numbers(
                unicode('from os import path\n'))))

    def test_unused_import_line_numbers_with_dot(self):
        self.assertEqual(
            [1],
            list(autoflake.unused_import_line_numbers(
                unicode('import os.path\n'))))

    def test_extract_package_name(self):
        self.assertEqual('os', autoflake.extract_package_name('import os'))
        self.assertEqual(
            'os', autoflake.extract_package_name('from os import path'))
        self.assertEqual(
            'os', autoflake.extract_package_name('import os.path'))

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

    def test_filter_code(self):
        self.assertEqual(
            """\
import os
os.foo()
""",
            ''.join(autoflake.filter_code(unicode("""\
import os
import re
os.foo()
"""))))

    def test_filter_code_with_from(self):
        self.assertEqual(
            """\
x = 1
""",
            ''.join(autoflake.filter_code(unicode("""\
from os import path
x = 1
"""))))

    def test_filter_code_with_from_and_inline(self):
        self.assertEqual(
            """\
from fake_foo import z  # foo, foo, zap
x = 1
""",
            ''.join(autoflake.filter_code(unicode("""\
from os import path  # foo
from fake_foo import z  # foo, foo, zap
x = 1
"""))))

    def test_filter_code_should_respect_noqa(self):
        self.assertEqual(
            """\
import re  # noqa
from subprocess import Popen  # NOQA
x = 1
""",
            ''.join(autoflake.filter_code(unicode("""\
from os import path  # foo
import re  # noqa
from subprocess import Popen  # NOQA
x = 1
"""))))

    def test_multiline_import(self):
        self.assertTrue(autoflake.multiline_import(r"""\
import os, \
    math, subprocess
"""))

        self.assertFalse(autoflake.multiline_import("""\
import os, math, subprocess
"""))

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

    def test_filter_code_should_ignore_multiline_imports(self):
        self.assertEqual(
            r"""\
import os
import os, \
    math, subprocess
os.foo()
""",
            ''.join(autoflake.filter_code(unicode(r"""\
import os
import re
import os, \
    math, subprocess
os.foo()
"""))))

    def test_filter_code_should_ignore_semicolons(self):
        self.assertEqual(
            r"""\
import os
import os; import math, subprocess
os.foo()
""",
            ''.join(autoflake.filter_code(unicode(r"""\
import os
import re
import os; import math, subprocess
os.foo()
"""))))

    def test_filter_code_should_ignore_non_standard_library(self):
        self.assertEqual(
            """\
import os
import my_own_module
from my_package import another_module
from my_package import subprocess
from my_blah.my_blah_blah import blah
os.foo()
""",
            ''.join(autoflake.filter_code(unicode("""\
import os
import my_own_module
import re
from my_package import another_module
from my_package import subprocess
from my_blah.my_blah_blah import blah
os.foo()
"""))))

    def test_filter_code_should_ignore_unsafe_imports(self):
        self.assertEqual(
            """\
import rlcompleter
print(1)
""",
            ''.join(autoflake.filter_code(unicode("""\
import rlcompleter
import sys
import io
import os
print(1)
"""))))

    def test_filter_code_should_ignore_docstring(self):
        line = unicode("""
def foo():
    '''
    >>> import math
    '''
""")
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
            ''.join(autoflake.fix_code(unicode("""\
import os
import re
import abc, math, subprocess
from sys import exit, version
os.foo()
math.pi
x = version
"""))))

    def test_detect_encoding_with_bad_encoding(self):
        with temporary_file('# -*- coding: blah -*-\n') as filename:
            self.assertEqual('latin-1',
                             autoflake.detect_encoding(filename))

    def test_useless_pass_line_numbers(self):
        self.assertEqual(
            [1],
            list(autoflake.useless_pass_line_numbers(
                unicode('pass\n'))))

        self.assertEqual(
            [],
            list(autoflake.useless_pass_line_numbers(
                unicode('if True:\n    pass\n'))))

    def test_useless_pass_line_numbers_with_more_complex(self):
        self.assertEqual(
            [6],
            list(autoflake.useless_pass_line_numbers(
                unicode("""\
if True:
    pass
else:
    True
    x = 1
    pass
"""))))

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
                unicode("""\
if True:
    pass
else:
    True
    x = 1
    pass
"""))))

    def test_filter_useless_pass_with_syntax_error(self):
        source = unicode("""\
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
""")

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
                unicode("""\
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
"""))))

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
                unicode("""\
import os
os.foo()
try:
    pass
    pass
except ImportError:
    pass
"""))))


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
    import os
except ImportError:
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

    def test_with_missing_pyflakes(self):
        with temporary_file('') as filename:
            output_file = io.StringIO()

            original_pyflakes = autoflake.PYFLAKES_BIN
            autoflake.PYFLAKES_BIN = 'non-existent-fake-program'
            try:
                with self.assertRaises(autoflake.MissingExecutableException):
                    autoflake.main(argv=['my_fake_program', filename],
                                   standard_out=output_file,
                                   standard_error=None)
            finally:
                autoflake.PYFLAKES_BIN = original_pyflakes

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
