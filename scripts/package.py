"""Deterministic install-folder archive; no source or exporter settings."""
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def package(folder=ROOT/'out/bejaia_saket'):
    folder = Path(folder)
    archive = folder.with_suffix('.zip')
    partial = archive.with_suffix('.zip.partial')
    with zipfile.ZipFile(partial, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as output:
        for path in sorted(folder.rglob('*')):
            if path.is_file():
                info = zipfile.ZipInfo(str(path.relative_to(folder.parent)), date_time=(1980,1,1,0,0,0))
                info.external_attr = 0o100644 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                output.writestr(info, path.read_bytes())
    partial.replace(archive)
    print(f'ZIP_OK path={archive} bytes={archive.stat().st_size}')
    return archive


if __name__ == '__main__':
    package()
