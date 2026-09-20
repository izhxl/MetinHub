"""Build a clean, updater-compatible release using an explicit allowlist."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from manutenzione_metin import https_url, versione


def build(output=None, url=None):
    version = (ROOT / 'VERSION.txt').read_text(encoding='utf-8').strip()
    versione(version)
    if url:
        https_url(url)
    names = [line.strip() for line in (ROOT / 'release-files.txt').read_text().splitlines()
             if line.strip() and not line.startswith('#')]
    if len(names) != len(set(name.lower() for name in names)):
        raise ValueError('Nomi duplicati in release-files.txt.')
    # Validate all inputs before creating an archive.
    for name in names:
        if '/' in name or '\\' in name or ':' in name or name.startswith('.'):
            raise ValueError('Nome non consentito: ' + name)
        if name.lower().endswith(('_settings.json', '_log.txt')) or name == 'install-state.json':
            raise ValueError('File personale escluso: ' + name)
        if not (ROOT / name).is_file() or (ROOT / name).is_symlink():
            raise ValueError('Risorsa mancante o collegata: ' + name)
    output = Path(output) if output else ROOT / 'dist'
    output.mkdir(parents=True, exist_ok=True)
    archive = output / ('MetinHub_' + version + '.zip')
    temporary = archive.with_suffix('.zip.tmp')
    try:
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as z:
            for name in names:
                data = (ROOT / name).read_bytes()
                if name == 'MetinHub_Launcher.cs':
                    data = re.sub(rb'AssemblyVersion\("[0-9.]+"\)',
                                  ('AssemblyVersion("' + version + '.0")').encode(), data)
                elif name == 'MetinHub.manifest':
                    data = re.sub(rb'assemblyIdentity version="[0-9.]+"',
                                  ('assemblyIdentity version="' + version + '.0"').encode(), data)
                z.writestr('MetinHub/' + name, data)
        temporary.replace(archive)
    finally:
        temporary.unlink(missing_ok=True)
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(sha + '  ' + archive.name + '\n')
    if url:
        manifest = dict(product='MetinHub', format=1, version=version,
                        url=url, sha256=sha, notes='MetinHub ' + version)
        (output / 'latest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(archive)
    return archive


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--url', help='URL HTTPS reale dello ZIP della release')
    args = parser.parse_args()
    build(args.out, args.url)
