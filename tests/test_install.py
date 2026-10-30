"""Installer regression tests; no LinuxCNC installation or hardware required."""
import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('installer', ROOT / 'scripts/install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)
BASE = '''[EMC]
MACHINE = test
[DISPLAY]
DISPLAY = gmoccapy
INCREMENTS = 5mm 1mm .5mm .1mm
MAX_LINEAR_VELOCITY = 12.5
[TRAJ]
COORDINATES = XYZ
[KINS]
JOINTS = 3
KINEMATICS = trivkins coordinates=XYZ
[HAL]
HALFILE = machine.hal
HALFILE = custom.hal
POSTGUI_HALFILE = postgui.hal
[JOINT_0]
HOME_SEQUENCE = 2
P = 1234
'''


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = Path(self.temp.name) / 'machine'
        self.config.mkdir()
        self.ini = self.config / 'test.ini'
        self.ini.write_text(BASE)
        (self.config / 'machine.hal').write_text('# hardware stays unchanged\n')
        (self.config / 'custom.hal').write_text('# custom\n')
        (self.config / 'postgui.hal').write_text(
            'net n iocontrol.0.tool-prep-number => gmoccapy.toolchange-number\n'
            'net c iocontrol.0.tool-change => gmoccapy.toolchange-change\n'
            'net d gmoccapy.toolchange-changed => iocontrol.0.tool-changed\n')
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def test_dry_run_writes_nothing(self):
        before = {p.relative_to(self.config): p.read_bytes() for p in self.config.rglob('*') if p.is_file()}
        installer.install(self.ini, dry_run=True)
        after = {p.relative_to(self.config): p.read_bytes() for p in self.config.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(list(self.config.parent.glob('*.backup-*')), [])

    def test_backup_and_migration_preserve_machine_parameters(self):
        backup = installer.install(self.ini)
        self.assertEqual((backup / self.ini.name).read_text(), BASE)
        text = self.ini.read_text()
        self.assertIn('DISPLAY = qtvcp -c qtvcp cnc_3axis_1024', text)
        self.assertIn('INCREMENTS = Continuous, 5mm, 1mm, .5mm, .1mm', text)
        self.assertEqual(installer.section_body(text, 'KINS')[1], installer.section_body(BASE, 'KINS')[1])
        self.assertEqual(installer.section_body(text, 'JOINT_0')[1], installer.section_body(BASE, 'JOINT_0')[1])
        self.assertEqual(installer.values(text, 'HAL', 'HALFILE'), ['machine.hal', 'custom.hal'])
        self.assertEqual((self.config / 'machine.hal').read_bytes(), (backup / 'machine.hal').read_bytes())
        self.assertNotIn('gmoccapy.', (self.config / 'postgui.hal').read_text())
        self.assertIn('hal_manualtoolchange.changed', (self.config / 'postgui.hal').read_text())

    def test_unknown_gmoccapy_pin_aborts_before_writes(self):
        (self.config / 'custom.hal').write_text('net unknown gmoccapy.some-machine-pin\n')
        with self.assertRaises(ValueError):
            installer.install(self.ini)
        self.assertEqual(self.ini.read_text(), BASE)
        self.assertEqual(list(self.config.parent.glob('*.backup-*')), [])

    def test_manual_toolchange_and_repeat_install(self):
        (self.config / 'postgui.hal').write_text('# no toolchanger\n')
        installer.install(self.ini, manual_toolchange=True)
        hal = (self.config / 'millpilot_postgui.hal').read_text()
        self.assertIn('iocontrol.0.tool-prepared', hal)
        self.assertIn('millpilot_postgui.hal', installer.values(self.ini.read_text(), 'HAL', 'POSTGUI_HALFILE'))
        pref = self.config / 'qtvcp/screens/cnc_3axis_1024/cnc_3axis_1024.pref'
        pref.write_text('keep my settings')
        installer.install(self.ini, manual_toolchange=True)
        self.assertEqual(pref.read_text(), 'keep my settings')
        self.assertEqual(installer.values(self.ini.read_text(), 'HAL', 'POSTGUI_HALFILE').count('millpilot_postgui.hal'), 1)

    def test_invalid_target(self):
        self.ini.write_text('[DISPLAY]\nDISPLAY = axis\n')
        with self.assertRaises(ValueError):
            installer.install(self.ini)


if __name__ == '__main__':
    unittest.main()
