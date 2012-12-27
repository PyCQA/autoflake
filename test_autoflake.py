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

    def test_unused_import_line_numbers(self):
        self.assertEqual(
            [1],
            list(autoflake.unused_import_line_numbers(
                unicode('import os\n'))))

    def test_standard_module_names(self):
        self.assertIn('os', list(autoflake.standard_module_names()))
        self.assertIn('subprocess', list(autoflake.standard_module_names()))

        self.assertNotIn('autoflake', list(autoflake.standard_module_names()))
        self.assertNotIn('pep8', list(autoflake.standard_module_names()))

    def test_filter_code(self):
        self.assertEqual(
            """\
import os
os.foo()
""",
            ''.join(autoflake.filter_code("""\
import os
import re
os.foo()
""")))

    def test_filter_code_should_ignore_complex_imports(self):
        self.assertEqual(
            """\
import os
import os, math, subprocess
os.foo()
""",
            ''.join(autoflake.filter_code("""\
import os
import re
import os, math, subprocess
os.foo()
""")))


class SystemTests(unittest.TestCase):

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


if __name__ == '__main__':
    unittest.main()

