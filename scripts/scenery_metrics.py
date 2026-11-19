"""Pixel measurements from cutout-aware ID renders and fixed projected bands."""
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def polygon_mask(size,polygons):
    image=Image.new('L',size)
    draw=ImageDraw.Draw(image)
    for polygon in polygons:
        points=np.asarray(polygon,float)
        if points.shape!=(4,2) or not np.isfinite(points).all():raise ValueError('Invalid projected band')
        draw.polygon([tuple(p) for p in points],fill=255)
    return np.asarray(image)>0


def measure_pixels(beauty,ids,bands):
    beauty=np.asarray(beauty);ids=np.asarray(ids)
    if beauty.shape!=ids.shape or beauty.ndim!=3 or beauty.shape[2]!=3:raise ValueError('Expected matching RGB images')
    green=ids[:,:,1].astype(float)/255
    foliage=np.where(green<=.04045,green/12.92,((green+.055)/1.055)**2.4)
    blue=ids[:,:,2].astype(float)/255
    barrier=np.where(blue<=.04045,blue/12.92,((blue+.055)/1.055)**2.4)
    red=ids[:,:,0].astype(float)/255
    terrain=np.where(red<=.04045,red/12.92,((red+.055)/1.055)**2.4)
    masks={};coverage={}
    for side,band in bands.items():
        band=np.asarray(band,bool)
        if band.shape!=foliage.shape or not band.any():raise ValueError('Empty or mismatched roadside band')
        count=int(band.sum());covered=float(foliage[band].sum());blocked=float(barrier[band].sum())
        coverage[side]=dict(band_pixels=count,foliage_pixels=covered,foliage_share=covered/count,passed=covered/count>=.9,
            fixed_barrier_pixels=blocked,foliage_share_excluding_fixed_barriers=covered/max(1,count-blocked))
        masks[side+'_band']=band
    combined=np.logical_or.reduce(list(bands.values()));height,width=combined.shape
    columns=np.where(combined.any(0))[0];top=combined[:,columns].argmax(0)
    roof=np.interp(np.arange(width),columns,top)
    hillside_roi=np.arange(height)[:,None]<roof[None,:]
    rgb=beauty.astype(float)/255;maximum=rgb.max(2);minimum=rgb.min(2)
    saturation=(maximum-minimum)/np.maximum(maximum,1e-9)
    pale=terrain*(hillside_roi&(rgb.mean(2)>.38)&(saturation<.32))
    masks.update(foliage=foliage,fixed_barriers=barrier,terrain=terrain,hillside_roi=hillside_roi,pale_hillside=pale)
    return dict(coverage=coverage,pale_hillside_pixels=float(pale.sum()),hillside_roi_pixels=int(hillside_roi.sum()),
                pale_hillside_share_of_frame=float(pale.mean()),pale_hillside_share_of_roi=float(pale.sum()/max(1,hillside_roi.sum()))),masks


def save_measurement(output,label,beauty,ids,bands,interval):
    output=Path(output);report,masks=measure_pixels(beauty,ids,bands)
    report['treated_station_interval_m']=list(interval)
    for name,mask in masks.items():Image.fromarray(np.uint8(np.clip(np.rint(mask.astype(float)*255),0,255))).save(output/(label+'_'+name+'.png'))
    overlay=np.asarray(beauty).copy()
    for side,color in [('left',(40,110,255)),('right',(255,80,220))]:
        band=masks[side+'_band'];overlay[band]=np.uint8(overlay[band]*.45+np.asarray(color)*.55)
    Image.fromarray(overlay).save(output/(label+'_bands_overlay.png'))
    (output/(label+'_metrics.json')).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


def compare_views(output):
    output=Path(output);result={}
    for suffix in ('','_exit_reverse'):
        before='before'+suffix;after='after'+suffix
        a=json.loads((output/(before+'_metrics.json')).read_text(encoding='utf-8'))
        b=json.loads((output/(after+'_metrics.json')).read_text(encoding='utf-8'))
        for name in ('left_band','right_band','hillside_roi'):
            if (output/(before+'_'+name+'.png')).read_bytes()!=(output/(after+'_'+name+'.png')).read_bytes():raise ValueError('Before/after measurement ROI differs')
        old=np.asarray(Image.open(output/(before+'_pale_hillside.png')))/255
        new=np.asarray(Image.open(output/(after+'_pale_hillside.png')))/255
        foliage=np.asarray(Image.open(output/(after+'_foliage.png')))/255
        previous_foliage=np.asarray(Image.open(output/(before+'_foliage.png')))/255
        hidden=np.minimum(np.maximum(0,old-new),np.maximum(0,foliage-previous_foliage))
        result[suffix or 'summit']=dict(before=a,after=b,baseline_pale_pixels=float(old.sum()),
            baseline_pale_remaining_pixels=float(np.minimum(old,new).sum()),baseline_pale_occluded_by_foliage_pixels=float(hidden.sum()),
            baseline_pale_occluded_by_foliage_share=float(hidden.sum()/max(1,old.sum())))
    (output/'visual_measurements.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result
