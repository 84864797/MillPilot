# 第三方说明

## LinuxCNC / QtVCP

MillPilot 通过系统安装的 LinuxCNC / QtVCP / QtPy 使用原生控件及接口，不在本仓库打包这些依赖的实现。其名称、商标和许可证归各自权利人所有。运行环境遵循各依赖自身许可证。

## Probe Basic 探测宏

`extras/probe-basic/subroutines/*.ngc` 来自 [kcjengr/probe_basic](https://github.com/kcjengr/probe_basic) 中的 `configs/probe_basic/subroutines/`，保留源文件作者与版本注释。作者包括 Chris P、TooTall18 等；以各文件原注释为准。原项目许可为 GNU GPL v3，许可证副本位于 `extras/probe-basic/LICENSE`。

这些文件未接入当前 MillPilot 基础界面，不由安装脚本启用。不要将其描述为已经完成实机验证的自动对刀或找中功能。

## 界面参考

gmoccapy 和 Probe Basic 为操作流程与分区的参考。MillPilot 使用 QtVCP，不使用 Probe Basic 的 QtPyVCP 界面文件，也不随包分发其图标、字体或整套界面资源。
