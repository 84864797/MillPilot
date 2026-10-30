#!/usr/bin/env python3
"""Offline real-QtVCP check. Controller data and machine/tool commands are mocked.
Run with system Python on a LinuxCNC installation, without launching the machine.
"""
import argparse
import ast
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SCREEN = ROOT / 'qtvcp/screens/cnc_3axis_1024'
parser = argparse.ArgumentParser()
parser.add_argument('--screenshots', type=Path)
args = parser.parse_args()
temp = tempfile.TemporaryDirectory()
config = Path(temp.name)
ini = config / 'check.ini'
ini.write_text('''[EMC]
MACHINE = MillPilot Demo
[DISPLAY]
DISPLAY = qtvcp cnc_3axis_1024
DEFAULT_SPINDLE_0_SPEED = 1000
MIN_SPINDLE_0_SPEED = 0
MAX_SPINDLE_0_SPEED = 12000
MAX_FEED_OVERRIDE = 1.2
DEFAULT_LINEAR_VELOCITY = 6
MAX_LINEAR_VELOCITY = 25
INCREMENTS = Continuous, 1 mm, 0.1 mm
[TRAJ]
COORDINATES = XYZ
LINEAR_UNITS = mm
MAX_LINEAR_VELOCITY = 25
[KINS]
JOINTS = 3
KINEMATICS = trivkins coordinates=XYZ
[EMCIO]
TOOL_TABLE = tool.tbl
[RS274NGC]
RS274NGC_STARTUP_CODE = G21 G40 G90 G94 G97 G64 P0.025
[SPINDLE_0]
MAX_FORWARD_VELOCITY = 12000
[AXIS_X]
MAX_VELOCITY = 25
MAX_ACCELERATION = 750
[AXIS_Y]
MAX_VELOCITY = 25
MAX_ACCELERATION = 750
[AXIS_Z]
MAX_VELOCITY = 25
MAX_ACCELERATION = 750
[JOINT_0]
TYPE = LINEAR
HOME_SEQUENCE = 2
[JOINT_1]
TYPE = LINEAR
HOME_SEQUENCE = 3
[JOINT_2]
TYPE = LINEAR
HOME_SEQUENCE = 1
''')
os.environ['INI_FILE_NAME'] = str(ini)
from qtvcp import logger
logger.initBaseLogger('millpilot-check', log_file=str(config / 'check.log'), log_level=logger.ERROR)
from PyQt5 import QtWidgets, QtCore, uic
import linuxcnc

app = QtWidgets.QApplication([])
class Window(QtWidgets.QMainWindow):
    def __getitem__(self, name):
        return getattr(self, name)
w = Window()
uic.loadUi(str(SCREEN / 'cnc_3axis_1024.ui'), w)
w.setStyleSheet((SCREEN / 'cnc_3axis_1024.qss').read_text())
spec = importlib.util.spec_from_file_location('millpilot_handler', SCREEN / 'cnc_3axis_1024_handler.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
# Validate API names on actual installed objects before replacing controller state.
for target_name in ['STATUS', 'ACTION', 'INFO']:
    target = getattr(m, target_name)
    tree = ast.parse((SCREEN / 'cnc_3axis_1024_handler.py').read_text())
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)
             and isinstance(n.value, ast.Name) and n.value.id == target_name}
    assert all(hasattr(target, a) for a in attrs), (target_name, attrs)
assert hasattr(m.STATUS.stat, 'poll')
class Pin(QtCore.QObject):
    value_changed = QtCore.pyqtSignal(float)
pin = Pin()
m.QHAL = SimpleNamespace(newpin=lambda *a: pin, HAL_FLOAT=2, HAL_IN=16)
status_methods = ['connect', 'is_homing', 'is_all_homed', 'is_man_mode', 'machine_is_on',
                  'estop_is_clear', 'is_auto_mode', 'is_spindle_on', 'get_jog_increment', 'get_jograte']
s = Mock(spec=['stat'] + status_methods)
s.stat = SimpleNamespace(poll=lambda: None, task_state=linuxcnc.STATE_ON,
                          interp_state=linuxcnc.INTERP_IDLE, inpos=True,
                          spindle=[{'enabled': False, 'direction': 0}])
s.is_homing.return_value = False
s.is_all_homed.return_value = False
s.is_spindle_on.side_effect = lambda number: s.stat.spindle[number]['enabled']
m.STATUS = s
m.ACTION = Mock()
h = m.HandlerClass(None, w, None)
h.initialized__()
assert w.spindle_speed_set.maximum() == 12000
assert w.spindle_speed_set.value() == 1000
assert w.gcode_graphics.background_color.name() == '#0c141b'
assert [w.spindleButtonLayout.itemAt(i).widget().objectName() for i in range(3)] == ['spindle_rev', 'spindle_stop', 'spindle_fwd']
assert [w.workspaceTabs.tabText(i) for i in range(6)] == ['刀路预览', '程序列表', '工件坐标', '刀具表', 'MDI', '设置']
assert w.startup_code_label.text().endswith('G64 P0.025')

w.spindle_speed_set.setValue(6000)
w.set_spindle_speed.click()
m.ACTION.SET_SPINDLE_ROTATION.assert_not_called()
m.ACTION.CALL_MDI.assert_not_called()
for direction, button in [(1, w.spindle_fwd), (-1, w.spindle_rev)]:
    button.click()
    m.ACTION.SET_SPINDLE_ROTATION.assert_called_with(direction, 6000, 0)
w.spindle_stop.click()
m.ACTION.SET_SPINDLE_STOP.assert_called_with(0)
s.stat.spindle[0].update(enabled=True, direction=-1)
w.spindle_speed_set.setValue(5000)
w.set_spindle_speed.click()
m.ACTION.SET_SPINDLE_ROTATION.assert_called_with(-1, 5000, 0)
for direction in [1, -1, 0]:
    s.stat.spindle[0].update(enabled=bool(direction), direction=direction)
    h.update_spindle_controls()
    assert w.spindle_fwd.isChecked() == (direction == 1)
    assert w.spindle_rev.isChecked() == (direction == -1)
    assert w.spindle_stop.isChecked() == (direction == 0)
for state in [linuxcnc.STATE_OFF, linuxcnc.STATE_ESTOP]:
    s.stat.task_state = state
    m.ACTION.reset_mock()
    h.start_spindle(1)
    h.home_all()
    assert not m.ACTION.mock_calls
s.stat.task_state = linuxcnc.STATE_ON
for homed in [False, True]:
    s.is_all_homed.return_value = homed
    m.ACTION.reset_mock()
    h.on_keycall_HOME(None, True, False, False)
    m.ACTION.SET_MACHINE_HOMING.assert_called_once_with(-1)
    m.ACTION.SET_MACHINE_UNHOMED.assert_not_called()
for condition in ['busy', 'paused', 'moving', 'homing']:
    s.stat.interp_state = (linuxcnc.INTERP_READING if condition == 'busy'
                          else linuxcnc.INTERP_PAUSED if condition == 'paused'
                          else linuxcnc.INTERP_IDLE)
    s.stat.inpos = condition != 'moving'
    s.is_homing.return_value = condition == 'homing'
    m.ACTION.reset_mock()
    h.home_all()
    m.ACTION.SET_MACHINE_HOMING.assert_not_called()
s.stat.interp_state = linuxcnc.INTERP_IDLE
s.stat.inpos = True
s.is_homing.return_value = False
real_info = m.INFO
for axes in ['XYZ', 'XYZA', 'XYZAC', 'XYZBC']:
    m.INFO = SimpleNamespace(AVAILABLE_AXES=list(axes), GET_JOG_FROM_NAME={a: i for i, a in enumerate(axes)})
    h.configure_axes_from_ini()
    slots = [('axisX', 'dro_x'), ('axisY', 'dro_y'), ('axisZ', 'dro_z'), ('axis4Label', 'dro_axis4'), ('axis5Label', 'dro_axis5')]
    for axis, (label, dro) in zip(axes, slots):
        assert getattr(w, label).text() == axis
        assert getattr(w, dro).property('Qjoint_number') == 'XYZABCUVW'.index(axis)
m.INFO = real_info
h.configure_axes_from_ini()
for value, expected in [(-10, 0), (36, 36), (160, 150)]:
    h.update_spindle_load(value)
    assert w.spindle_load_bar.value() == expected
w.PREFS_ = Mock()
w.settings_keyboard_jog.setChecked(False)
assert not h.keyboard_jog_enabled
w.PREFS_.putpref.assert_called_with('keyboard_jog', False, bool, 'SCREEN_OPTIONS')
w.settings_preview_dro.setChecked(True)
assert w.gcode_graphics.property('_dro')
with patch.object(m.hal, 'component_exists', return_value=False), patch.object(m.QtWidgets.QMessageBox, 'information') as message:
    w.settings_ladder.click()
    message.assert_called_once()
from qtvcp.widgets import action_button
for name, method in [('settings_scope', 'load_halscope'), ('settings_status', 'load_status'),
                     ('settings_meter', 'load_halmeter'), ('settings_calibration', 'load_calibration'),
                     ('settings_halshow', 'load_halshow')]:
    with patch.object(action_button.AUX_PRGM, method) as launch:
        getattr(w, name).action()
        launch.assert_called_once()

from qtvcp.widgets.dialog_widget import CalculatorDialog
calc = CalculatorDialog(w)
calc.clearAll()
calc.digitButtons[4].click()
calc.plusButton.click()
calc.digitButtons[2].click()
calc.equalButton.click()
assert float(calc.display.text()) == 6

if args.screenshots:
    args.screenshots.mkdir(parents=True, exist_ok=True)
    w.PREFS_ = None
    h.spindle_control_timer.stop()
    # Display-only placeholders: no controller or real machine is represented.
    for name, text in [('machine_state', '已停止'), ('machine_state_bottom', '已停止'),
                       ('work_offset_label', 'G54'), ('tool_number', 'T0'),
                       ('spindle_speed', '0 rpm'), ('loaded_file', '未加载程序'),
                       ('feed_override_value', '100%'), ('rapid_override_value', '100%'),
                       ('jog_rate_value', '360'), ('clock', '2026-10-30  12:00:00')]:
        getattr(w, name).setText(text)
    s.stat.task_state = linuxcnc.STATE_OFF
    h.update_home_controls()
    h.update_spindle_controls()
    h.update_spindle_load(0)
    w.btn_machine_on.setText('设备关闭')
    w.spindle_speed_set.setValue(1000)
    w.spindle_fwd.setChecked(False)
    w.spindle_rev.setChecked(False)
    w.spindle_stop.setChecked(True)
    w.workspaceTabs.setCurrentWidget(w.settingsPage)
    w.settingsTabs.setCurrentIndex(0)
    w.show()
    app.processEvents()
    w.grab().save(str(args.screenshots / 'settings.png'))
    calc.show()
    app.processEvents()
    calc.grab().save(str(args.screenshots / 'calculator.png'))
    calc.close()
print('PASS: real QtVCP UI/API, startup, axis mapping, spindle/home callbacks, settings tools, saved options and calculator. Controller/HAL outputs mocked; no machine motion.')
w.close()
temp.cleanup()
