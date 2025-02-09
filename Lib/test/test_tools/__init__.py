"""Support functions for testing scripts in the Tools directory."""
import contextlib
import importlib
import os.path
import unittest
from test import support
from test.support import import_helper
from pathlib import Path


if not support.has_subprocess_support:
    raise unittest.SkipTest("test module requires subprocess")


basepath = os.path.normpath(
        os.path.dirname(                 # <src/install dir>
            os.path.dirname(                # Lib
                os.path.dirname(                # test
                    os.path.dirname(__file__)))))    # test_tools

toolsdir = os.path.join(basepath, 'Tools')
scriptsdir = os.path.join(toolsdir, 'scripts')

def skip_if_missing(tool=None):
    if tool:
        tooldir = os.path.join(toolsdir, tool)
    else:
        tool = 'scripts'
        tooldir = scriptsdir
    if not os.path.isdir(tooldir):
        raise unittest.SkipTest(f'{tool} directory could not be found')

@contextlib.contextmanager
def imports_under_tool(name, *subdirs):
    tooldir = os.path.join(toolsdir, name, *subdirs)
    with import_helper.DirsOnSysPath(tooldir) as cm:
        yield cm

def import_tool(toolname):
    with import_helper.DirsOnSysPath(scriptsdir):
        return importlib.import_module(toolname)

def load_tests(*args):
    return support.load_package_tests(os.path.dirname(__file__), *args)


class SnapshotTestCase(unittest.TestCase):
    # def __init__(self):
    #     self.path = None

    def _is_update(self):
        import sys
        return any(arg == '--snapshot-update' for arg in sys.argv)

    def assert_snapshot_equal(self, snapshot_dir, actual, snapshot):
        path = Path(snapshot_dir) / snapshot
        if self._is_update():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(actual, encoding='utf-8')
            msg = f"Snapshot updated: {path}"
            self.fail(msg)
        else:
            expected = path.read_text(encoding='utf-8')
            self.assertEqual(expected, actual)