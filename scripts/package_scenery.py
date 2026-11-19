"""Build a separate, install-ready summit folder and Content Manager ZIP."""
import json
from pathlib import Path
import re
import shutil
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def package(source=ROOT/'out/scenery_qualification/summit',destination=ROOT/'out/install_ready',track_id='bejaia_saket_summit'):
    source=Path(source);destination=Path(destination)
    if not re.fullmatch('[a-z0-9_]+',track_id):raise ValueError('Invalid track ID')
    if destination.resolve().is_relative_to(source.resolve()):raise ValueError('Install destination must be separate from qualification')
    for name in ('bejaia_saket.kn5','data/surfaces.ini','ui/ui_track.json','extension/ext_config.ini','extension/trees/trees.txt'):
        if not (source/name).is_file():raise ValueError('Missing qualification file: '+name)
    metadata=json.loads((source/'ui/ui_track.json').read_text(encoding='utf-8'))
    target=destination/track_id;archive=destination/(track_id+'.zip')
    if target.exists() or archive.exists():raise FileExistsError('Install output already exists')
    destination.mkdir(parents=True,exist_ok=True);target.mkdir()
    for name in ('ai','data','extension','ui'):
        if (source/name).is_dir():shutil.copytree(source/name,target/name)
    for name in ('map.png','CREDITS.md','PILOT_ASSET_CREDITS.md','PILOT_ASSET_LICENSES.json'):
        if (source/name).is_file():shutil.copy2(source/name,target/name)
    shutil.copyfile(source/'bejaia_saket.kn5',target/(track_id+'.kn5'))
    (target/'models.ini').write_text('[MODEL_0]\nFILE='+track_id+'.kn5\nPOSITION=0,0,0\nROTATION=0,0,0\n',encoding='utf-8')
    metadata['name']='RN24 Béjaïa–Saket — Summit 3D shrub qualification'
    metadata['description']='Separate full-route installation with summit-only 880–1180 m scenery. Linux preview/static checks only; native AC/CSP/Pure and FPS unverified.'
    (target/'ui/ui_track.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (target/'README.txt').write_text('Install '+track_id+' under content/tracks; does not replace the main route.\nSummit-only scenery qualification: 880–1180 m. Native AC/CSP/Pure and FPS unverified.\n',encoding='utf-8')
    files=sorted(p for p in target.rglob('*') if p.is_file())
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as output:
        for path in files:
            info=zipfile.ZipInfo('content/tracks/'+track_id+'/'+path.relative_to(target).as_posix(),(2020,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            output.writestr(info,path.read_bytes())
    return dict(folder=str(target),zip=str(archive),files=len(files),folder_bytes=sum(p.stat().st_size for p in files),zip_bytes=archive.stat().st_size)


if __name__=='__main__':print('SUMMIT_INSTALL_PACKAGE_OK',json.dumps(package(),ensure_ascii=True))
