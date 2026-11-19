"""Report pure placement plans without touching any Blender/install/cache artifacts."""
import argparse
import json
from pathlib import Path

import numpy as np

from scenery_placement import CONFIG, load_zones, plan_sectors

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zones',type=Path,default=CONFIG)
    parser.add_argument('--centerline',type=Path,default=ROOT/'data/centerline.npz')
    parser.add_argument('--models',type=Path,default=ROOT/'data/pilot300/treefx_models.json')
    args=parser.parse_args();config=load_zones(args.zones)
    with np.load(args.centerline) as source:data=dict(source)
    models=json.loads(args.models.read_text())
    results=plan_sectors(data,models,config['report_sectors'],zones=config['main'])
    for name,result in results.items():print('SCENERY_SECTOR',name,json.dumps(result['report']))


if __name__=='__main__':main()
