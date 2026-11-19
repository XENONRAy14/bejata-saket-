"""Portable metadata helpers for the qualification preview."""
import math
import configparser
from pathlib import Path


def resolve_model(track):
    track=Path(track).resolve();manifest=track/'models.ini'
    if manifest.is_file():
        config=configparser.ConfigParser();config.read(manifest,encoding='utf-8')
        if not config.has_option('MODEL_0','FILE'):raise ValueError('Missing MODEL_0 FILE in '+str(manifest))
        model=(track/config['MODEL_0']['FILE']).resolve()
        if not model.is_relative_to(track):raise ValueError('Model must be inside track folder')
        if not model.is_file():raise FileNotFoundError(model)
        return model
    for model in (track/(track.name+'.kn5'),track/'bejaia_saket.kn5'):
        if model.is_file():return model
    raise FileNotFoundError('No track model in '+str(track))


def tree_lod(config,distance):
    if not math.isfinite(distance) or distance<0:raise ValueError('Invalid camera distance')
    lower=0
    for section in sorted((s for s in config.sections() if s.startswith('LOD_')),key=lambda s:int(s[4:])):
        upper=float(config[section]['DISTANCE'])
        if not math.isfinite(upper) or upper<=lower:raise ValueError('Invalid TreeFX LOD ranges')
        if lower<=distance<upper:return int(section[4:])
        lower=upper
    return None
