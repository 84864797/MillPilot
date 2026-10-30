"""MillPilot: 1024 x 768 LinuxCNC QtVCP mill screen.

SPDX-License-Identifier: GPL-3.0-only
"""

import hal
import linuxcnc
from qtpy import QtCore, QtWidgets

from qtvcp.core import Action, Info, Qhal, Status
from qtvcp.lib.keybindings import Keylookup
from qtvcp.widgets.gcode_editor import GcodeEditor
from qtvcp.widgets.mdi_line import MDILine


STATUS = Status()
ACTION = Action()
INFO = Info()
QHAL = Qhal()
KEYBIND = Keylookup()


class HandlerClass:
    def __init__(self, halcomp, widgets, paths):
        self.hal = halcomp
        self.w = widgets
        self.paths = paths

    def initialized__(self):
        """Set a deterministic startup page and expose a fullscreen shortcut."""
        self.w.workspaceTabs.setCurrentIndex(0)
        startup_code = INFO.INI.find("RS274NGC", "RS274NGC_STARTUP_CODE") or ""
        startup_text = "RS274NGC_STARTUP_CODE = {}".format(startup_code)
        self.w.startup_code_label.setText(startup_text)
        self.w.startup_code_label.setToolTip(startup_text)
        self.w.startup_code_label.setVisible(bool(startup_code))
        self.w.setWindowTitle("MillPilot 铣控 — {}".format(
            INFO.INI.find("EMC", "MACHINE") or "LinuxCNC"))
        self.configure_axes_from_ini()
        self.initialize_settings()
        self.w.spindle_speed_set.setRange(
            INFO.MIN_SPINDLE_0_SPEED, INFO.MAX_SPINDLE_0_SPEED)
        self.w.spindle_speed_set.setValue(INFO.DEFAULT_SPINDLE_0_SPEED)
        self.w.set_spindle_speed.clicked.connect(self.apply_spindle_speed)
        self.w.btn_home_all.clicked.connect(self.home_all)
        self.w.spindle_fwd.clicked.connect(lambda: self.start_spindle(1))
        self.w.spindle_rev.clicked.connect(lambda: self.start_spindle(-1))
        self.w.spindle_stop.clicked.connect(self.stop_spindle)
        self.spindle_control_timer = QtCore.QTimer(self.w)
        self.spindle_control_timer.timeout.connect(self.update_spindle_controls)
        self.spindle_control_timer.timeout.connect(self.update_home_controls)
        self.spindle_control_timer.start(100)
        self.update_spindle_controls()
        self.update_home_controls()
        self.w.tool_add.clicked.connect(self.add_tool)
        self.w.tool_delete.clicked.connect(self.delete_checked_tools)
        self.w.tool_edit.clicked.connect(self.edit_current_tool_cell)
        self.w.tool_reload.clicked.connect(lambda: ACTION.RELOAD_TOOLTABLE())
        self.spindle_load_pin = QHAL.newpin(
            "spindle-load", QHAL.HAL_FLOAT, QHAL.HAL_IN
        )
        self.spindle_load_pin.value_changed.connect(self.update_spindle_load)
        KEYBIND.add_call("Key_F11", "on_keycall_F11")

    def initialize_settings(self):
        prefs = getattr(self.w, "PREFS_", None)
        self.keyboard_jog_enabled = (
            prefs.getpref("keyboard_jog", True, bool, "SCREEN_OPTIONS")
            if prefs else True)
        preview_dro = (prefs.getpref("preview_dro", False, bool, "SCREEN_OPTIONS")
                       if prefs else False)
        self.w.settings_keyboard_jog.setChecked(self.keyboard_jog_enabled)
        self.w.settings_preview_dro.setChecked(preview_dro)
        self.w.gcode_graphics.setProperty("_dro", preview_dro)
        self.w.settings_fullscreen.setChecked(self.w.isFullScreen())
        self.w.settings_keyboard_jog.toggled.connect(self.set_keyboard_jog_enabled)
        self.w.settings_preview_dro.toggled.connect(self.set_preview_dro)
        self.w.settings_fullscreen.toggled.connect(self.set_fullscreen)
        self.w.settings_reset_view.clicked.connect(
            lambda: ACTION.SET_GRAPHICS_VIEW("p"))
        self.w.settings_ladder.clicked.connect(self.open_ladder)
        self.w.settingsTabs.setCurrentIndex(0)
        ini = INFO.INI
        self.w.settings_machine_info.setText(
            "机床：{}\n坐标轴：{}\n运动学：{}\n"
            "最大直线速度：{} mm/s\n主轴最高转速：{} rpm\n"
            "刀具表：{}\n启动代码：{}".format(
                ini.find("EMC", "MACHINE") or "—", " ".join(INFO.AVAILABLE_AXES),
                ini.find("KINS", "KINEMATICS") or "—",
                ini.find("TRAJ", "MAX_LINEAR_VELOCITY") or "—",
                ini.find("SPINDLE_0", "MAX_FORWARD_VELOCITY") or "—",
                ini.find("EMCIO", "TOOL_TABLE") or "—",
                ini.find("RS274NGC", "RS274NGC_STARTUP_CODE") or "—"))

    def save_screen_option(self, name, value):
        prefs = getattr(self.w, "PREFS_", None)
        if prefs:
            prefs.putpref(name, value, bool, "SCREEN_OPTIONS")

    def set_keyboard_jog_enabled(self, enabled):
        self.keyboard_jog_enabled = enabled
        self.save_screen_option("keyboard_jog", enabled)

    def set_preview_dro(self, enabled):
        self.w.gcode_graphics.setProperty("_dro", enabled)
        self.save_screen_option("preview_dro", enabled)

    def set_fullscreen(self, enabled):
        if enabled:
            self.w.showFullScreen()
        else:
            self.w.showNormal()

    def open_ladder(self):
        if not hal.component_exists("classicladder_rt"):
            QtWidgets.QMessageBox.information(
                self.w, "梯形图", "当前机床尚未加载 ClassicLadder 实时组件。\n"
                "请先在机床 HAL 中配置 classicladder_rt 后再打开梯形图。")
            return
        from qtvcp.lib.aux_program_loader import Aux_program_loader
        Aux_program_loader().load_ladder()

    def configure_axes_from_ini(self):
        """Bind the five screen slots to [TRAJ] COORDINATES via QtVCP Info."""
        axes = list(INFO.AVAILABLE_AXES)[:5]
        axis_slots = (
            ("axisRowX", "axisX", "home_x", "dro_x", "zero_x"),
            ("axisRowY", "axisY", "home_y", "dro_y", "zero_y"),
            ("axisRowZ", "axisZ", "home_z", "dro_z", "zero_z"),
            ("axisRow4", "axis4Label", "home_axis4", "dro_axis4", "zero_axis4"),
            ("axisRow5", "axis5Label", "home_axis5", "dro_axis5", "zero_axis5"),
        )
        jog_slots = (
            ("jog_x_neg", "jog_x_pos"),
            ("jog_y_neg", "jog_y_pos"),
            ("jog_z_neg", "jog_z_pos"),
            ("jog_axis4_neg", "jog_axis4_pos"),
            ("jog_axis5_neg", "jog_axis5_pos"),
        )

        axis_count = len(axes)
        row_height = {3: 80, 4: 60, 5: 48}.get(axis_count, 48)
        self.w.axis_config_label.setText("{}轴 {}".format(axis_count, "".join(axes)))
        self.w.axisPanel.setProperty("axisCount", str(axis_count))

        for slot, names in enumerate(axis_slots):
            row, label, led, dro, zero = (self.w[name] for name in names)
            jog_neg, jog_pos = (self.w[name] for name in jog_slots[slot])
            if slot >= axis_count:
                row.hide()
                jog_neg.hide()
                jog_pos.hide()
                continue

            axis = axes[slot]
            axis_index = "XYZABCUVW".index(axis)
            jog_number = INFO.GET_JOG_FROM_NAME.get(axis)
            if jog_number is None:
                jog_number = axis_index
            row.setMinimumHeight(row_height)
            label.setText(axis)
            dro.setProperty("Qjoint_number", axis_index)
            led.setProperty("joint_number_status", jog_number)
            zero.setProperty("axis_letter", axis)
            zero.setProperty("joint_number", axis_index)

            for button, positive in ((jog_neg, False), (jog_pos, True)):
                button.setText("{}{}".format(axis, "＋" if positive else "－"))
                button.setProperty("axis_letter", axis)
                button.setProperty("joint_number", jog_number)

        self.w.axisPanel.style().unpolish(self.w.axisPanel)
        self.w.axisPanel.style().polish(self.w.axisPanel)

    def processed_key_event__(
        self, receiver, event, is_pressed, key, code, shift, cntrl
    ):
        """Route typing to editors while retaining the emergency shortcuts."""
        emergency_keys = (
            QtCore.Qt.Key_Escape,
            QtCore.Qt.Key_F1,
            QtCore.Qt.Key_F2,
        )

        if code not in emergency_keys:
            current = receiver
            while current is not None:
                if isinstance(
                    current,
                    (QtWidgets.QDialog, QtWidgets.QAbstractSpinBox, MDILine, GcodeEditor),
                ):
                    if is_pressed:
                        receiver.keyPressEvent(event)
                    event.accept()
                    return True
                current = current.parent()

        if event.isAutoRepeat():
            return True

        return KEYBIND.manage_function_calls(
            self, event, is_pressed, key, shift, cntrl
        )

    def home_all_unavailable_reason(self):
        STATUS.stat.poll()
        if STATUS.stat.task_state != linuxcnc.STATE_ON:
            return "请先解除急停并开启设备"
        if STATUS.is_homing():
            return "正在回零，请等待完成；需要中止时按停止或 Esc"
        if STATUS.stat.interp_state != linuxcnc.INTERP_IDLE:
            return "请先停止正在执行或暂停的程序"
        if not STATUS.stat.inpos:
            return "请先停止点动，等待机床静止"
        if not INFO.HOME_ALL_FLAG:
            return "全部回零需要为所有关节配置 HOME_SEQUENCE"
        return ""

    def update_home_controls(self):
        reason = self.home_all_unavailable_reason()
        homing = STATUS.is_homing()
        homed = STATUS.is_all_homed()
        button = self.w.btn_home_all
        button.setEnabled(not reason)
        button.setChecked(homed and not homing)
        button.setText("回零中…" if homing else "全部回零")
        button.setToolTip(reason or (
            "全部已回零；再次点击将重新执行 INI 回零顺序，不取消回零标记"
            if homed else "按 INI 的 HOME_SEQUENCE 顺序执行全部关节回零"))

    def home_all(self):
        if self.home_all_unavailable_reason():
            self.update_home_controls()
            return
        # QtVCP switches to MANUAL and joint mode, then sends home(-1).
        # Deliberately avoid ActionButton's home/unhome toggle behavior.
        ACTION.SET_MACHINE_HOMING(-1)

    def spindle_manual_ready(self):
        """An idle controller can switch from AUTO/MDI to manual spindle control."""
        STATUS.stat.poll()
        return (STATUS.stat.task_state == linuxcnc.STATE_ON
                and STATUS.stat.interp_state == linuxcnc.INTERP_IDLE)

    def update_spindle_controls(self):
        ready = self.spindle_manual_ready()
        state = STATUS.stat
        if state.task_state != linuxcnc.STATE_ON:
            hint = "请先解除急停并开启设备"
        elif state.interp_state != linuxcnc.INTERP_IDLE:
            hint = "程序正在执行或暂停，请先停止程序"
        else:
            hint = "按设定转速控制主轴"
        for name in ("spindle_fwd", "spindle_rev", "spindle_stop", "set_spindle_speed"):
            self.w[name].setEnabled(ready)
            self.w[name].setToolTip(hint)
        spindle = state.spindle[0]
        running = bool(spindle['enabled'])
        direction = spindle['direction'] if running else 0
        self.w.spindle_fwd.setChecked(direction == 1)
        self.w.spindle_rev.setChecked(direction == -1)
        self.w.spindle_stop.setChecked(not running)

    def apply_spindle_speed(self):
        """Update a running spindle without entering MDI or starting a stopped one."""
        if not self.spindle_manual_ready():
            return
        if STATUS.is_spindle_on(0):
            direction = STATUS.stat.spindle[0]['direction']
            if direction in (-1, 1):
                ACTION.SET_SPINDLE_ROTATION(
                    direction, self.w.spindle_speed_set.value(), 0)

    def start_spindle(self, direction):
        if not self.spindle_manual_ready():
            return
        rpm = self.w.spindle_speed_set.value()
        if rpm <= 0:
            return
        ACTION.SET_MANUAL_MODE()
        ACTION.SET_SPINDLE_ROTATION(direction, rpm, 0)

    def stop_spindle(self):
        if self.spindle_manual_ready():
            ACTION.SET_SPINDLE_STOP(0)

    def update_spindle_load(self, value):
        """Clamp the VFD load feedback to the Probe Basic-style 0–150% scale."""
        load = max(0.0, min(150.0, float(value)))
        self.w.spindle_load_bar.setValue(round(load))
        self.w.spindle_load_value.setText("{:.0f}%".format(load))
        color = "#45c5e6" if load < 100 else "#e2bf3f" if load < 125 else "#db4b55"
        self.w.spindle_load_bar.setStyleSheet(
            "QProgressBar::chunk { background: %s; border-radius: 3px; }" % color
        )

    def add_tool(self):
        """Append a blank tool row that can be edited in place."""
        self.w.tool_offsets.add_tool()

    def delete_checked_tools(self):
        """Delete rows selected using the ToolOffsetView checkbox column."""
        checked = self.w.tool_offsets.get_checked_list()
        if not checked:
            return
        answer = QtWidgets.QMessageBox.question(
            self.w,
            "删除刀具",
            "确定删除已勾选的 {} 个刀具吗？".format(len(checked)),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if answer != QtWidgets.QMessageBox.Yes:
            return
        self.w.tool_offsets.delete_tools()

    def edit_current_tool_cell(self):
        """Open the touchscreen dialog for the selected tool-table cell."""
        index = self.w.tool_offsets.currentIndex()
        if index.isValid():
            self.w.tool_offsets.showSelection(index)

    def _keyboard_jog(self, state, joint, direction, fast=False):
        """Jog only in manual mode with machine power enabled."""
        if state and not getattr(self, "keyboard_jog_enabled", True):
            return
        if not STATUS.is_man_mode() or not STATUS.machine_is_on():
            return

        distance = STATUS.get_jog_increment()
        rate = STATUS.get_jograte() / 60.0
        if fast:
            rate *= 2.0

        if state:
            ACTION.JOG(joint, direction, rate, distance)
        else:
            ACTION.JOG(joint, 0, 0, 0)

    def _keyboard_jog_axis(self, state, axis, direction, fast=False):
        joint = INFO.GET_JOG_FROM_NAME.get(axis)
        if joint is not None:
            self._keyboard_jog(state, joint, direction, fast)

    # Standard QtVCP key calls.  F1/Escape remain active even while entering MDI.
    def on_keycall_ESTOP(self, event, state, shift, cntrl):
        if state:
            ACTION.SET_ESTOP_STATE(STATUS.estop_is_clear())

    def on_keycall_POWER(self, event, state, shift, cntrl):
        if state:
            ACTION.SET_MACHINE_STATE(not STATUS.machine_is_on())

    def on_keycall_HOME(self, event, state, shift, cntrl):
        if state:
            self.home_all()

    def on_keycall_ABORT(self, event, state, shift, cntrl):
        if state:
            ACTION.ABORT()

    def on_keycall_XPOS(self, event, state, shift, cntrl):
        self._keyboard_jog_axis(state, "X", 1, shift)

    def on_keycall_XNEG(self, event, state, shift, cntrl):
        self._keyboard_jog_axis(state, "X", -1, shift)

    def on_keycall_YPOS(self, event, state, shift, cntrl):
        self._keyboard_jog_axis(state, "Y", 1, shift)

    def on_keycall_YNEG(self, event, state, shift, cntrl):
        self._keyboard_jog_axis(state, "Y", -1, shift)

    def on_keycall_ZPOS(self, event, state, shift, cntrl):
        self._keyboard_jog_axis(state, "Z", 1, shift)

    def on_keycall_ZNEG(self, event, state, shift, cntrl):
        self._keyboard_jog_axis(state, "Z", -1, shift)

    def on_keycall_APOS(self, event, state, shift, cntrl):
        self._keyboard_jog_axis(state, "A", 1, shift)

    def on_keycall_ANEG(self, event, state, shift, cntrl):
        self._keyboard_jog_axis(state, "A", -1, shift)

    def on_keycall_BPOS(self, event, state, shift, cntrl):
        self._keyboard_jog_axis(state, "B", 1, shift)

    def on_keycall_BNEG(self, event, state, shift, cntrl):
        self._keyboard_jog_axis(state, "B", -1, shift)

    def on_keycall_CPOS(self, event, state, shift, cntrl):
        self._keyboard_jog_axis(state, "C", 1, shift)

    def on_keycall_CNEG(self, event, state, shift, cntrl):
        self._keyboard_jog_axis(state, "C", -1, shift)

    def on_keycall_F11(self, event, state, shift, cntrl):
        if not state:
            return
        self.w.settings_fullscreen.setChecked(not self.w.isFullScreen())

    def __getitem__(self, item):
        return getattr(self, item)

    def __setitem__(self, item, value):
        return setattr(self, item, value)


def get_handlers(halcomp, widgets, paths):
    return [HandlerClass(halcomp, widgets, paths)]
