# 常见问题

## 找不到屏幕、handler 或自定义控件

核对文件应位于：

```text
机床目录/qtvcp/screens/cnc_3axis_1024/cnc_3axis_1024.ui
机床目录/qtvcp/screens/cnc_3axis_1024/cnc_3axis_1024_handler.py
机床目录/qtvcp/screens/cnc_3axis_1024/cnc_3axis_1024.qss
```

INI 使用 `DISPLAY = qtvcp -c qtvcp cnc_3axis_1024`。不要只更新 UI 或 handler；三份文件一起更新。Python 依赖用系统版本，不要用 pip 的 Qt 包覆盖 LinuxCNC 环境。

## 启动出现 AttributeError 或 setColumnStretch 错误

早期版本存在不正确的布局属性、残留的探测控件引用及 `STATUS.poll()` 调用。更新当前版本三份屏幕文件，关闭旧进程后重新启动。QtVCP 状态刷新应使用 `STATUS.stat.poll()`。保留完整 traceback，以最底部的异常及文件行号定位问题。

## 提示找不到 INTRO_GRAPHIC / INTRO_TIME

这两项是可选启动画面设置。若后面另有 traceback，应优先处理真正导致退出的异常。无需为了消除提示给 INI 添加不存在的图片路径。

## 主轴按钮灰色

先解除急停并开启设备，停止正在执行或暂停的程序。悬停查看按钮提示。没有输入正转速时方向按钮不会启动主轴。若界面是旧版，可能因为发送 MDI 后未恢复模式；请成套更新屏幕文件。

## 主轴方向按钮高亮，但主轴没有动作 / 实际转速为 0

高亮来自控制器状态。检查原 HAL 的主轴启用、方向、PWM / 模拟量与驱动器状态。反转需要实际方向接线；不要任意把信号映射到空闲 GPIO。没有真实转速反馈时，“实际转速”可能一直为 0。界面不把指令值冒充测量值。

## 全部回零不能点击，或者没有轴运动

开启设备、停止程序和点动，等待机床静止。全部关节必须配置 `HOME_SEQUENCE`。正在回零时按钮暂时禁用。若 `HOME_SEARCH_VEL`、`HOME_LATCH_VEL` 都为 0，配置属于当前位置建立基准，不能据此期待自动寻找开关。需要物理寻零时按机床实际开关接线配置，而不是在 UI 里猜测方向。

## 换刀等待不结束 / gmoccapy 引脚不存在

参见 [换刀接入说明](INSTALL.md#手动换刀)。QtVCP 内置对话框使用 `hal_manualtoolchange.number/change/changed`，不是 `gmoccapy.toolchange-*`。同时检查 `iocontrol.0.tool-prepare/tool-prepared`。已有 ATC / remap 时保留原流程。安装器只迁移直接列在 INI 中的本地 HAL 文件，额外 source 文件需单独检查。

## 梯形图无法打开

只有运行中的 HAL 已加载 `classicladder_rt`，才可启动 ClassicLadder 用户界面。MillPilot 不会自动加载实时组件或创建梯形图逻辑。

## 诊断工具点了没有窗口

确认系统安装了 `halscope`、`halmeter`、`linuxcnctop`，以及 LinuxCNC 的 `halshow.tcl` / `emccalib.tcl`。通过正常 LinuxCNC 启动器启动界面，以获得 TCL 路径和 INI 环境。检查终端错误输出。独立诊断工具不继承 MillPilot 的 Qt 主题。

## 刀路预览空白 / OpenGL 错误

检查显卡驱动、OpenGL 与远程桌面的图形支持。离线 `QT_QPA_PLATFORM=offscreen` 检查仅用于控件加载与回调，不验证真实 OpenGL 刀路绘制。实际运行不要使用 offscreen 参数。

## 安装失败

`--dry-run` 可先检查变更。目标必须是完整机床 INI，不能使用 `examples/display.ini.example`。原配置存在其他 gmoccapy 专用引脚时，安装器会退出，要求按机器含义人工迁移。安装中途发生文件系统错误时，使用输出的完整备份恢复。

## 报告问题

请提供 LinuxCNC 版本、安装方式、轴组合、完整异常日志和复现步骤；涉及机床 I/O 时，附去除私人信息的相关 INI / HAL 片段。不要上传自己的整个配置目录或密码、网络凭据。
