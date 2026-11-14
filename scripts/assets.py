"""Download only checksum-pinned CC0 source maps; never refresh a lock implicitly."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
USER_AGENT = 'bejaia_saket-assets/2.0'


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def download(url, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix+'.partial')
    try:
        subprocess.run(['curl','--fail','--location','--silent','--show-error',
                        '--retry','2','--connect-timeout','15','--max-time','180',
                        '--user-agent',USER_AGENT,url,'--output',str(partial)], check=True)
        return partial
    except Exception:
        partial.unlink(missing_ok=True)
        raise


def acquire(root=ROOT, manifest=None):
    root = Path(root)
    manifest = manifest if manifest is not None else json.loads((root/'data/assets.lock.json').read_text())
    if manifest.get('version') != 1 or not manifest.get('assets'):
        raise ValueError('Need a nonempty version 1 asset lock')
    count = 0
    for asset in manifest['assets']:
        if asset['license'] != 'CC0-1.0' or not asset.get('id'):
            raise ValueError('Only identified CC0 assets are allowed')
        for entry in asset['files'].values():
            relative = Path(entry['path'])
            if relative.is_absolute() or '..' in relative.parts or relative.parts[:2] != ('data','asset_cache'):
                raise ValueError('Asset cache path outside data/asset_cache')
            target = root/relative
            if target.exists():
                if sha256(target) != entry['sha256']:
                    raise ValueError(f'Corrupt cached asset: {target}; remove explicitly to re-download')
            else:
                partial = download(entry['url'], target)
                if sha256(partial) != entry['sha256']:
                    partial.unlink()
                    raise ValueError(f'Asset checksum mismatch: {asset["id"]}')
                partial.replace(target)
            count += 1
    print(f'ASSETS_OK assets={len(manifest["assets"])} files={count} sha256_verified=True')
    return manifest


if __name__ == '__main__':
    acquire()
