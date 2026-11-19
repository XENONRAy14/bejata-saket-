"""Portable metadata helpers for the qualification preview."""
import math


def tree_lod(config,distance):
    if not math.isfinite(distance) or distance<0:raise ValueError('Invalid camera distance')
    lower=0
    for section in sorted((s for s in config.sections() if s.startswith('LOD_')),key=lambda s:int(s[4:])):
        upper=float(config[section]['DISTANCE'])
        if not math.isfinite(upper) or upper<=lower:raise ValueError('Invalid TreeFX LOD ranges')
        if lower<=distance<upper:return int(section[4:])
        lower=upper
    return None
