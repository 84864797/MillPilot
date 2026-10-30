"""Static regressions usable on GitHub Actions without a LinuxCNC install."""
import ast
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SCREEN = ROOT / 'qtvcp/screens/cnc_3axis_1024'


class SourceTests(unittest.TestCase):
    def test_handler_python_and_status_access(self):
        tree = ast.parse((SCREEN / 'cnc_3axis_1024_handler.py').read_text())
        forbidden = {'poll', 'interp_state', 'tool_in_spindle'}
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == 'STATUS':
                self.assertNotIn(node.attr, forbidden, 'Controller data belongs under STATUS.stat')

    def test_ui_names_and_grid_stretch(self):
        tree = ET.parse(SCREEN / 'cnc_3axis_1024.ui')
        names = [w.get('name') for w in tree.iter('widget')]
        self.assertEqual(len(names), len(set(names)))
        self.assertIn('settingsPage', names)
        for p in tree.iter('property'):
            self.assertNotIn(p.get('name'), ['columnStretch', 'rowStretch'])
        main = next(e for e in tree.iter('layout') if e.get('name') == 'mainGrid')
        self.assertEqual(main.get('columnstretch'), '30,23,23,23')

    def test_markdown_local_links_exist(self):
        for doc in [ROOT / 'README.md', *list((ROOT / 'docs').glob('*.md'))]:
            for target in re.findall(r'\]\(([^\s)]+)\)', doc.read_text()):
                if '://' not in target and not target.startswith('#'):
                    self.assertTrue((doc.parent / target.split('#')[0]).exists(), (doc.name, target))


if __name__ == '__main__':
    unittest.main()
