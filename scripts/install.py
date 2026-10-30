#!/usr/bin/env python3
"""Install MillPilot into an existing LinuxCNC machine config, with a backup.
SPDX-License-Identifier: GPL-3.0-only
"""
import argparse
from datetime import datetime
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
SCREEN = 'cnc_3axis_1024'
SCREEN_FILES = [f'{SCREEN}.ui', f'{SCREEN}.qss', f'{SCREEN}_handler.py']
TOOLCHANGE = {
    'gmoccapy.toolchange-number': 'hal_manualtoolchange.number',
    'gmoccapy.toolchange-change': 'hal_manualtoolchange.change',
    'gmoccapy.toolchange-changed': 'hal_manualtoolchange.changed',
}
MANUAL_HAL = '''# MillPilot / QtVCP manual tool-change dialog
net millpilot-tool-number iocontrol.0.tool-prep-number => hal_manualtoolchange.number
net millpilot-tool-change iocontrol.0.tool-change => hal_manualtoolchange.change
net millpilot-tool-changed hal_manualtoolchange.changed => iocontrol.0.tool-changed
'''


def section_body(text, section):
    pattern = r'(?ms)^\[' + re.escape(section) + r'\][^\n]*\n(.*?)(?=^\[|\Z)'
    return re.search(pattern, text)


def values(text, section, key):
    match = section_body(text, section)
    if not match:
        return []
    return re.findall(r'(?mi)^\s*' + re.escape(key) + r'\s*=\s*([^\n;#]+)', match[1])


def set_value(text, section, key, value):
    match = section_body(text, section)
    line = f'{key} = {value}\n'
    if not match:
        return text.rstrip() + f'\n\n[{section}]\n' + line
    body = match[1]
    pattern = r'(?mi)^\s*' + re.escape(key) + r'\s*=.*\n?'
    if re.search(pattern, body):
        body = re.sub(pattern, lambda _: line, body)
    else:
        body = body.rstrip('\n') + '\n' + line
    return text[:match.start(1)] + body + text[match.end(1):]


def install(ini_path, dry_run=False, manual_toolchange=False):
    ini = Path(ini_path).expanduser().resolve()
    if not ini.is_file() or ini.suffix.lower() != '.ini':
        raise ValueError('请指定已存在的机床 .ini 文件。')
    config = ini.parent
    if ROOT == config or ROOT.is_relative_to(config):
        raise ValueError('请将 MillPilot 源码放在机床配置目录之外，避免备份递归。')
    for name in SCREEN_FILES:
        if not (ROOT / 'qtvcp/screens' / SCREEN / name).is_file():
            raise ValueError(f'安装包缺少 {name}')
    original = ini.read_text(encoding='utf-8')
    if not values(original, 'KINS', 'JOINTS') or not values(original, 'TRAJ', 'COORDINATES'):
        raise ValueError('目标 INI 缺少 KINS/JOINTS 或 TRAJ/COORDINATES；不能用示例片段代替机床配置。')
    text = set_value(original, 'DISPLAY', 'DISPLAY', f'qtvcp -c qtvcp {SCREEN}')
    # QtVCP expects comma-separated increments; preserve the user's distances.
    increments = values(original, 'DISPLAY', 'INCREMENTS')
    if increments:
        old = increments[0].strip()
        if ',' not in old:
            tokens = re.findall(r'(?:Continuous|continuous)|[-+]?\d*\.?\d+(?:\s*(?:mm|cm|um|inch|in|mil))?', old)
            old = ', '.join(t.strip() for t in tokens)
        if not re.search(r'(?i)continuous', old):
            old = 'Continuous, ' + old
        text = set_value(text, 'DISPLAY', 'INCREMENTS', old)
    else:
        text = set_value(text, 'DISPLAY', 'INCREMENTS', 'Continuous, 1 mm, 0.1 mm, 0.01 mm')

    writes = {}
    hal_paths = []
    for key in ['HALFILE', 'POSTGUI_HALFILE']:
        for entry in values(original, 'HAL', key):
            name = entry.strip()
            path = (config / name).resolve()
            if path.is_relative_to(config) and path.is_file():
                hal_paths.append(path)
    migrated = 0
    all_hal = ''
    for path in set(hal_paths):
        content = path.read_text(encoding='utf-8')
        updated = content
        for old, new in TOOLCHANGE.items():
            if old in updated:
                migrated += 1
                updated = updated.replace(old, new)
        # Other gmoccapy-only pins require a machine-specific mapping.
        active = '\n'.join(line.split('#', 1)[0] for line in updated.splitlines())
        if 'gmoccapy.' in active:
            raise ValueError(f'{path.name} 存在其他 gmoccapy 专用引脚，请先按 docs/INSTALL.md 处理。')
        all_hal += active + '\n'
        if updated != content:
            writes[path] = updated
    if manual_toolchange:
        if 'iocontrol.0.tool-change' in all_hal:
            if migrated == 0 and 'hal_manualtoolchange.' not in all_hal:
                raise ValueError('现有配置已连接换刀逻辑，请勿另加手动换刀。')
        else:
            name = 'millpilot_postgui.hal'
            path = config / name
            if path.exists():
                raise ValueError(f'{name} 已存在，请检查其内容后手动接入，安装程序不会覆盖。')
            writes[path] = MANUAL_HAL
            if 'iocontrol.0.tool-prepared' not in all_hal:
                writes[path] += ('net millpilot-tool-prepared iocontrol.0.tool-prepare '
                                 '=> iocontrol.0.tool-prepared\n')
            existing = values(text, 'HAL', 'POSTGUI_HALFILE')
            if existing:
                match = section_body(text, 'HAL')
                body = match[1].rstrip('\n') + '\nPOSTGUI_HALFILE = ' + name + '\n'
                text = text[:match.start(1)] + body + text[match.end(1):]
            else:
                text = set_value(text, 'HAL', 'POSTGUI_HALFILE', name)
    writes[ini] = text
    print(f'目标机床：{ini}')
    print(f'安装界面：{config / "qtvcp/screens" / SCREEN}')
    print(f'迁移 gmoccapy 换刀引脚：{migrated} 项')
    for path in writes:
        print(f'更新配置：{path.relative_to(config)}')
    if dry_run:
        print('预览完成，未修改任何文件。')
        return None
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup = config.with_name(config.name + '.backup-millpilot-' + stamp)
    shutil.copytree(config, backup, symlinks=True)
    destination = config / 'qtvcp/screens' / SCREEN
    destination.mkdir(parents=True, exist_ok=True)
    for name in SCREEN_FILES:
        shutil.copy2(ROOT / 'qtvcp/screens' / SCREEN / name, destination / name)
    for path, content in writes.items():
        path.write_text(content, encoding='utf-8')
    print(f'完整备份：{backup}')
    print('安装完成。使用原机床 INI 启动 LinuxCNC；速度、回零、运动学和硬件接线保持原配置。')
    return backup


def main():
    parser = argparse.ArgumentParser(description='MillPilot 安装/更新：备份现有机床后接入 QtVCP 界面。')
    parser.add_argument('ini', help='现有机床 INI 文件路径')
    parser.add_argument('--dry-run', action='store_true', help='只预览，不修改文件')
    parser.add_argument('--manual-toolchange', action='store_true', help='没有换刀逻辑时接入 QtVCP 手动换刀确认')
    args = parser.parse_args()
    try:
        install(args.ini, args.dry_run, args.manual_toolchange)
    except (ValueError, OSError) as error:
        print(f'安装未完成：{error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
