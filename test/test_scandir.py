"""Tests for scandir.scandir()."""

import os
import shutil
import sys
import time
import unittest

try:
    import scandir
    has_scandir = True
except ImportError:
    has_scandir = False

FILE_ATTRIBUTE_DIRECTORY = 16

try:
    from test import support
    test_path = support.TESTFN
except ImportError:
    test_path = u'@test_{0}_tmp'.format(os.getpid())
# TODO ben: test_path = r'C:\work\scandir\TESTDIR'

IS_PY3 = sys.version_info >= (3, 0)

if IS_PY3:
    int_types = int
else:
    int_types = (int, long)
    str = unicode


if hasattr(os, 'symlink'):
    try:
        link_name = os.path.join(os.path.dirname(__file__), '_testlink')
        os.symlink(__file__, link_name)
        os.remove(link_name)
        symlinks_supported = True
    except NotImplementedError:
        # Windows versions before Vista don't support symbolic links
        symlinks_supported = False
else:
    symlinks_supported = False


def create_file(path, contents='1234'):
    with open(path, 'w') as f:
        f.write(contents)


class TestMixin(object):
    def setUp(self):
        join = os.path.join

        os.mkdir(test_path)
        os.mkdir(join(test_path, 'subdir'))
        create_file(join(test_path, 'file1.txt'))
        create_file(join(test_path, 'file2.txt'), contents='12345678')

        os.mkdir(join(test_path, 'subdir', u'unidir\u018F'))
        create_file(join(test_path, 'subdir', 'file1.txt'))
        create_file(join(test_path, 'subdir', u'unicod\u018F.txt'))

        create_file(join(test_path, 'subdir', u'unidir\u018F', 'file1.txt'))

        os.mkdir(join(test_path, 'linkdir'))

        if not symlinks_supported:
            return

        os.mkdir(join(test_path, 'linkdir', 'linksubdir'))
        create_file(join(test_path, 'linkdir', 'file1.txt'))

        os.symlink(os.path.abspath(join(test_path, 'linkdir', 'file1.txt')),
                   join(test_path, 'linkdir', 'link_to_file'))

        dir_name = os.path.abspath(join(test_path, 'linkdir', 'linksubdir'))
        dir_link = join(test_path, 'linkdir', 'link_to_dir')
        if sys.version_info >= (3, 3):
            # "target_is_directory" was only added in Python 3.3
            os.symlink(dir_name, dir_link, target_is_directory=True)
        else:
            os.symlink(dir_name, dir_link)

    def tearDown(self):
        try:
            shutil.rmtree(test_path)
        except OSError:
            # why does the above fail sometimes?
            time.sleep(0.1)
            shutil.rmtree(test_path)

    if not hasattr(unittest.TestCase, 'skipTest'):
        def skipTest(self, reason):
            sys.stdout.write('skipped {0!r} '.format(reason))

    def test_basic(self):
        entries = sorted(self.scandir_func(test_path), key=lambda e: e.name)
        self.assertEqual([(e.name, e.is_dir()) for e in entries],
                         [('file1.txt', False), ('file2.txt', False),
                          ('linkdir', True), ('subdir', True)])
        self.assertEqual([e.path for e in entries],
                         [os.path.join(test_path, e.name) for e in entries])

    def test_dir_entry(self):
        entries = dict((e.name, e) for e in self.scandir_func(test_path))
        e = entries['file1.txt']
        self.assertEqual([e.is_dir(), e.is_file(), e.is_symlink()], [False, True, False])
        e = entries['file2.txt']
        self.assertEqual([e.is_dir(), e.is_file(), e.is_symlink()], [False, True, False])
        e = entries['subdir']
        self.assertEqual([e.is_dir(), e.is_file(), e.is_symlink()], [True, False, False])

        self.assertEqual(entries['file1.txt'].stat().st_size, 4)
        self.assertEqual(entries['file2.txt'].stat().st_size, 8)

    def test_stat(self):
        entries = list(self.scandir_func(test_path))
        for entry in entries:
            os_stat = os.stat(os.path.join(test_path, entry.name))
            scandir_stat = entry.stat()
            self.assertEqual(os_stat.st_mode, scandir_stat.st_mode)
            self.assertEqual(int(os_stat.st_mtime), int(scandir_stat.st_mtime))
            self.assertEqual(int(os_stat.st_ctime), int(scandir_stat.st_ctime))
            if entry.is_file():
                self.assertEqual(os_stat.st_size, scandir_stat.st_size)

    def test_returns_iter(self):
        it = self.scandir_func(test_path)
        entry = next(it)
        assert hasattr(entry, 'name')

    def check_file_attributes(self, result):
        self.assertTrue(hasattr(result, 'st_file_attributes'))
        self.assertTrue(isinstance(result.st_file_attributes, int_types))
        self.assertTrue(0 <= result.st_file_attributes <= 0xFFFFFFFF)

    def test_file_attributes(self):
        if sys.platform != 'win32' or not self.has_file_attributes:
            # st_file_attributes is Win32 specific (but can't use
            # unittest.skipUnless on Python 2.6)
            return self.skipTest('st_file_attributes not supported')

        entries = dict((e.name, e) for e in self.scandir_func(test_path))

        # test st_file_attributes on a file (FILE_ATTRIBUTE_DIRECTORY not set)
        result = entries['file1.txt'].stat()
        self.check_file_attributes(result)
        self.assertEqual(result.st_file_attributes & FILE_ATTRIBUTE_DIRECTORY, 0)

        # test st_file_attributes on a directory (FILE_ATTRIBUTE_DIRECTORY set)
        result = entries['subdir'].stat()
        self.check_file_attributes(result)
        self.assertEqual(result.st_file_attributes & FILE_ATTRIBUTE_DIRECTORY,
                         FILE_ATTRIBUTE_DIRECTORY)

    def test_path(self):
        entries = sorted(self.scandir_func(test_path), key=lambda e: e.name)
        self.assertEqual([os.path.basename(e.name) for e in entries],
                         ['file1.txt', 'file2.txt', 'linkdir', 'subdir'])
        self.assertEqual([os.path.normpath(os.path.join(test_path, e.name)) for e in entries],
                         [os.path.normpath(e.path) for e in entries])

    def test_symlink(self):
        if not symlinks_supported:
            return self.skipTest('symbolic links not supported')

        entries = sorted(self.scandir_func(os.path.join(test_path, 'linkdir')),
                         key=lambda e: e.name)

        self.assertEqual([(e.name, e.is_symlink()) for e in entries],
                         [('file1.txt', False),
                          ('link_to_dir', True),
                          ('link_to_file', True),
                          ('linksubdir', False)])

        self.assertEqual([(e.name, e.is_file(), e.is_file(follow_symlinks=False))
                          for e in entries],
                         [('file1.txt', True, True),
                          ('link_to_dir', False, False),
                          ('link_to_file', True, False),
                          ('linksubdir', False, False)])

        self.assertEqual([(e.name, e.is_dir(), e.is_dir(follow_symlinks=False))
                          for e in entries],
                         [('file1.txt', False, False),
                          ('link_to_dir', True, False),
                          ('link_to_file', False, False),
                          ('linksubdir', True, True)])

    def test_bytes(self):
        # Check that unicode filenames are returned correctly as bytes in output
        path = os.path.join(test_path, 'subdir').encode(sys.getfilesystemencoding(), 'replace')
        self.assertTrue(isinstance(path, bytes))
        entries = [e for e in self.scandir_func(path) if e.name.startswith(b'unicod')]
        self.assertEqual(len(entries), 1)
        entry = entries[0]

        self.assertTrue(isinstance(entry.name, bytes))
        self.assertTrue(isinstance(entry.path, bytes))

        # b'unicod?.txt' on Windows, b'unicod\xc6\x8f.txt' (UTF-8) or similar on POSIX
        entry_name = u'unicod\u018f.txt'.encode(sys.getfilesystemencoding(), 'replace')
        self.assertEqual(entry.name, entry_name)
        self.assertEqual(entry.path, os.path.join(path, entry_name))

    def test_unicode(self):
        # Check that unicode filenames are returned correctly as (unicode) str in output
        path = os.path.join(test_path, 'subdir')
        if not IS_PY3:
            path = path.decode(sys.getfilesystemencoding(), 'replace')
        self.assertTrue(isinstance(path, str))
        entries = [e for e in self.scandir_func(path) if e.name.startswith('unicod')]
        self.assertEqual(len(entries), 1)
        entry = entries[0]

        self.assertTrue(isinstance(entry.name, str))
        self.assertTrue(isinstance(entry.path, str))

        entry_name = u'unicod\u018f.txt'
        self.assertEqual(entry.name, entry_name)
        self.assertEqual(entry.path, os.path.join(path, u'unicod\u018f.txt'))

        # Check that it handles unicode input properly
        path = os.path.join(test_path, 'subdir', u'unidir\u018f')
        self.assertTrue(isinstance(path, str))
        entries = list(self.scandir_func(path))
        self.assertEqual(len(entries), 1)
        entry = entries[0]

        self.assertTrue(isinstance(entry.name, str))
        self.assertTrue(isinstance(entry.path, str))
        self.assertEqual(entry.name, 'file1.txt')
        self.assertEqual(entry.path, os.path.join(path, 'file1.txt'))

    # TODO ben: add tests for file not found is_dir/is_file/stat


if has_scandir:
    class TestScandirGeneric(TestMixin, unittest.TestCase):
        def setUp(self):
            self.scandir_func = scandir.scandir_generic
            self.has_file_attributes = False
            TestMixin.setUp(self)


    if hasattr(scandir, 'scandir_python'):
        class TestScandirPython(TestMixin, unittest.TestCase):
            def setUp(self):
                self.scandir_func = scandir.scandir_python
                self.has_file_attributes = True
                TestMixin.setUp(self)


    if hasattr(scandir, 'scandir_c'):
        class TestScandirC(TestMixin, unittest.TestCase):
            def setUp(self):
                self.scandir_func = scandir.scandir_c
                self.has_file_attributes = True
                TestMixin.setUp(self)


if hasattr(os, 'scandir'):
    class TestScandirOS(TestMixin, unittest.TestCase):
        def setUp(self):
            self.scandir_func = os.scandir
            self.has_file_attributes = True
            TestMixin.setUp(self)
