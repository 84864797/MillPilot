#!/usr/bin/env python3
"""Build a clean source/install archive without configs, caches or old previews."""
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = ['README.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md', 'CHANGELOG.md', 'VERSION',
           'docs', 'examples', 'qtvcp', 'scripts', 'tests', 'extras']


def main():
    version = (ROOT / 'VERSION').read_text().strip()
    output = ROOT / 'dist' / f'MillPilot-{version}.zip'
    output.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in ALLOWED:
            path = ROOT / name
            for file in sorted(path.rglob('*')) if path.is_dir() else [path]:
                if file.is_file() and '__pycache__' not in file.parts and file.suffix not in ['.pyc', '.log', '.pref']:
                    archive.write(file, str(Path(f'MillPilot-{version}') / file.relative_to(ROOT)))
    print(output)


if __name__ == '__main__':
    main()
