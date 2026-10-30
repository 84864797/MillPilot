# 安装、更新与回退

## 1. 准备运行环境

MillPilot 是 LinuxCNC 的显示界面，不是独立控制器，也不包含 Mesa 驱动或通用整机配置。先准备：

- 一套能够用原界面正常启动的 LinuxCNC 2.9 机床配置。
- 系统提供的 QtVCP、Python 3、PyQt5 / QtPy、Qt OpenGL 与 QScintilla 依赖。推荐使用 LinuxCNC 提供的系统安装方式，避免把系统 QtVCP 与 pip 虚拟环境混用。
- 可用的显卡 / OpenGL 环境和中文字体；Noto Sans CJK 或文泉驿微黑均可。
- 1024×768 或更大的显示屏。桌面面板占用屏幕时，可用 F11 全屏。

本项目在 LinuxCNC 2.9.8 环境核对接口并进行离线测试；其他版本须自行验证。安装前可检查：

```bash
command -v linuxcnc
command -v qtvcp
/usr/bin/python3 -c 'import linuxcnc, qtpy; print(qtpy.API_NAME)'
```

如果缺少 QtVCP 或控件依赖，按 [LinuxCNC 官方 QtVCP 文档](https://linuxcnc.org/docs/stable/html/gui/qtvcp.html) 修复当前系统环境；本项目没有需要通过 pip 安装的 Python 依赖。

## 2. 下载

```bash
git clone https://github.com/84864797/MillPilot.git
cd MillPilot
```

或者在仓库页面选择 **Code → Download ZIP**，解压后在该目录打开终端。源码目录不要放在机床配置目录内部。

以下示例中的 `my_machine/my_machine.ini` 需要替换为自己的路径。一个目录有多个 INI 时，应明确选择实际启动的那份 INI。

## 3. 关闭 LinuxCNC，先预览再安装

```bash
python3 scripts/install.py ~/linuxcnc/configs/my_machine/my_machine.ini --dry-run
python3 scripts/install.py ~/linuxcnc/configs/my_machine/my_machine.ini
```

脚本会：

1. 检查目标 INI 含现有的关节数和坐标轴配置。
2. 将整个机床目录复制到同级的 `my_machine.backup-millpilot-日期时间`。
3. 安装 `qtvcp/screens/cnc_3axis_1024/` 中的三个运行文件。
4. 把 `[DISPLAY] DISPLAY` 改为 `qtvcp -c qtvcp cnc_3axis_1024`。
5. 保留点动步距数值，转换为 QtVCP 使用的逗号分隔格式并添加 Continuous。
6. 将直接列在 `[HAL] HALFILE / POSTGUI_HALFILE` 本地文件中的三种标准 gmoccapy 换刀引脚迁移至 `hal_manualtoolchange.*`。

脚本不修改回零速度、轴行程、PID、Mesa 针脚、主轴接线、运动学或启动 G 代码。显示参数中的主轴最低/最高转速应与机器真实参数一致；界面的转速输入框按 `MIN_SPINDLE_0_SPEED` / `MAX_SPINDLE_0_SPEED` 限制。

### 手动换刀

原配置通过 gmoccapy 的标准三根换刀引脚连接时，安装脚本会迁移：

| 旧引脚 | QtVCP 引脚 |
| --- | --- |
| `gmoccapy.toolchange-number` | `hal_manualtoolchange.number` |
| `gmoccapy.toolchange-change` | `hal_manualtoolchange.change` |
| `gmoccapy.toolchange-changed` | `hal_manualtoolchange.changed` |

若原配置**没有任何换刀逻辑**，并且需要人工装刀后的确认弹窗：

```bash
python3 scripts/install.py ~/linuxcnc/configs/my_machine/my_machine.ini --manual-toolchange
```

这会增加 `millpilot_postgui.hal` 与对应 `POSTGUI_HALFILE`，不会直接把换刀完成信号短接。已有 ATC / remap 配置不要使用该选项。

已有独立 `hal_manualtoolchange` 用户组件时，QtVCP 会沿用它的引脚及独立确认窗口；若要使用 MillPilot 主题的内置弹窗，应移除旧的独立用户组件加载行，并保留三根换刀连接。不要让两套换刀确认组件同时管理同一流程。

其他 `gmoccapy.*` 专用引脚、HAL 中通过 `source` 再引入的文件、动态生成的 Tcl 接线或位于机床目录外的 HAL，需手动核对；安装器不会猜测其硬件含义。遇到未知 gmoccapy 引脚会在备份及写入前退出。

## 4. 用原 INI 启动

```bash
linuxcnc ~/linuxcnc/configs/my_machine/my_machine.ini
```

也可以继续使用原来的 LinuxCNC 启动器选择此机床。屏幕正式名称为 MillPilot 铣控，内部标识仍为 `cnc_3axis_1024`；目录、UI 和 handler 文件名须成套保留。

首次启动先保持急停，核对轴名、单位、限位、回零状态和硬件信号，再进行低速点动、主轴与冷却测试。最后空运行验证程序加载、启动、暂停和停止。

## 5. 主轴与反馈接入

界面只向 LinuxCNC 发命令，实际电气动作仍由原 HAL 决定：

- 正反转需要对应的 VFD / 驱动器方向接线和配置；单独有正转输出不等于具备反转功能。
- “实际转速”读取真实反馈。没有转速反馈时可能保持 0，不能将其作为未发送指令的唯一判断依据。
- 负载表创建 `qtvcp.spindle-load` 浮点输入，范围为 0–150%。负载源必须输出百分比，不能直接连接未经换算的电压/电流。

按 `examples/millpilot_postgui.hal.example` 接入需要的信号。示例中的占位引脚不能原样启用。若改变 `qtvcp -c` 的组件名，也要同步修改负载引脚前缀。

## 6. 多轴与回零

显示轴由 `[TRAJ] COORDINATES` 读取，最多 5 轴，例如 `XYZ`、`XYZA`、`XYZAC`、`XYZBC`。保留自己机床的 `[KINS] KINEMATICS`、`JOINTS` 和 `[DISPLAY] GEOMETRY`，尤其不要把五轴机床的真实运动学替换为三轴示例。

全部回零由 LinuxCNC 按 `[JOINT_n] HOME_SEQUENCE` 排序执行。每个关节都必须有相应顺序。界面不规定一定是 Z/X/Y，也不改变搜索方向或速度；按钮与 Home 键会检查电源、解释器、静止状态及是否已在回零。已回零后再点击会重新执行回零，不会取消回零标记。搜索及锁存速度均为零的配置是在当前位置建立基准，不等同于开关寻零。

## 7. 可选启动代码

在原 INI 的 `[RS274NGC]` 节中按机床需要添加，例如：

```ini
[RS274NGC]
RS274NGC_STARTUP_CODE = G21 G40 G90 G94 G97 G64 P0.025
```

这是解释器的启动模式，`G21` 选择毫米，`G64 P0.025` 涉及路径公差。示例仅适合相应单位和工艺要求，安装器不会自动添加。配置存在时在底部显示；不存在时隐藏该文字。

## 8. 更新

关闭 LinuxCNC，在源码目录执行：

```bash
git pull --ff-only
python3 scripts/install.py ~/linuxcnc/configs/my_machine/my_machine.ini --dry-run
python3 scripts/install.py ~/linuxcnc/configs/my_machine/my_machine.ini
```

每次安装都会完整备份。现有 `cnc_3axis_1024.pref` 设置文件不会被覆盖。

## 9. 回退

关闭 LinuxCNC，找到脚本输出的完整备份目录。可以直接用备份中的原 INI 启动，也可以恢复到原目录：

```bash
# 使用实际的备份目录替换日期时间占位部分
cp -a ~/linuxcnc/configs/my_machine.backup-millpilot-日期时间/. \
  ~/linuxcnc/configs/my_machine/
```

原显示配置和 HAL 恢复后，再使用原 INI 启动。新安装的屏幕文件即使留在目录里也不会被旧 DISPLAY 调用。

## 10. 手动安装

需要人工审核每处接线时，可不使用安装脚本：

```bash
mkdir -p ~/linuxcnc/configs/my_machine/qtvcp/screens
cp -a qtvcp/screens/cnc_3axis_1024 \
  ~/linuxcnc/configs/my_machine/qtvcp/screens/
```

先备份原配置，将 `examples/display.ini.example` 的必要键合并到现有同名节，按上文迁移换刀连接，然后启动原 INI。示例是片段，不能直接作为整机配置运行。
