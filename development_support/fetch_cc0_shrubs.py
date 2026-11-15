"""Fetch an additional CC0 shrub from Poly Haven into the development assets only."""
from pathlib import Path
import hashlib,json,urllib.request

WORK=Path(__file__).resolve().parent
folder=WORK/'assets/searsia_lucida'
folder.mkdir(exist_ok=True)
def fetch(url):
    request=urllib.request.Request(url,headers={'User-Agent':'Bejaia-Saket-CC0-asset-build/1.0'})
    with urllib.request.urlopen(request,timeout=120) as response:return response.read()
metadata=json.loads(fetch('https://api.polyhaven.com/files/searsia_lucida'))
entry=metadata['blend']['1k']['blend']
files={'searsia_lucida_1k.blend':entry,**entry['include']}
for name,record in files.items():
    destination=folder/name
    if destination.is_file() and hashlib.md5(destination.read_bytes()).hexdigest()==record['md5']:continue
    blob=fetch(record['url'])
    if len(blob)!=record['size'] or hashlib.md5(blob).hexdigest()!=record['md5']:raise ValueError('Asset integrity: '+name)
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_bytes(blob)
    print('CC0_DOWNLOAD_OK',name,len(blob),flush=True)
manifest=dict(asset='searsia_lucida',source='https://polyhaven.com/a/searsia_lucida',license='CC0-1.0',license_source='https://polyhaven.com/license',botany='South African source species; visual small-leaf shrub surrogate, not claimed native to Algeria',files={k:{x:v[x] for x in ('url','size','md5')} for k,v in files.items()})
(folder/'SOURCE.json').write_text(json.dumps(manifest,indent=2))
licenses_path=WORK/'asset_licenses.json'
licenses=json.loads(licenses_path.read_text())
licenses['poly_haven_shrub']={k:manifest[k] for k in ('asset','source','license','license_source','botany')}
licenses_path.write_text(json.dumps(licenses,indent=2))
print('SHRUB_SOURCE_VERIFIED')
