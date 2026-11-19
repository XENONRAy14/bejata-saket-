"""Fail on any physical mesh, AC empty or guard visual record change."""
import argparse
import json
from pathlib import Path

from scenery_kn5 import validate_lock


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate',type=Path)
    parser.add_argument('--reference',type=Path,default=Path(__file__).resolve().parents[1]/'out/bejaia_saket/bejaia_saket.kn5')
    args=parser.parse_args()
    print('PHYSICS_LOCK_OK',json.dumps(validate_lock(args.reference,args.candidate)))
