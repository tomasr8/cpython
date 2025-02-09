import subprocess
import sys
import unittest
from pathlib import Path
from test.support import REPO_ROOT, TEST_HOME_DIR, requires_subprocess
from test.test_tools import skip_if_missing


pygettext = Path(REPO_ROOT) / 'Tools' / 'i18n' / 'pygettext.py'


def _generate_po_file(path, *, stdout_only=True):
    res = subprocess.run([sys.executable, pygettext,
                          '--no-location', '--omit-header',
                          '-o', '-', path],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True)
    if stdout_only:
        return res.stdout
    return res


def _get_snapshot_path(module_name):
    return Path(TEST_HOME_DIR) / 'translationdata' / module_name / 'messages.pot'


@requires_subprocess()
class TestTranslationsBase(unittest.TestCase):

    def assertMsgidsEqual(self, module):
        '''Assert that msgids extracted from a given module match a
        snapshot.

        '''
        skip_if_missing('i18n')
        res = _generate_po_file(module.__file__, stdout_only=False)
        self.assertEqual(res.returncode, 0)
        self.assertEqual(res.stderr, '')
        snapshot_path = _get_snapshot_path(module.__name__)
        snapshot = snapshot_path.read_text(encoding='utf-8')
        self.assertListEqual(res.stdout, snapshot)


def update_translation_snapshots(module):
    contents = _generate_po_file(module.__file__)
    snapshot_path = _get_snapshot_path(module.__name__)
    snapshot_path.write_text(contents, encoding='utf-8')
