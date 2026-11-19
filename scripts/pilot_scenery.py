"""Deterministic, layered roadside scenery made only from the project's CC0 sources."""
from pathlib import Path

from pilot_common import DATA, Image, np, foliage_image_metrics
from scenery_placement import edge_layout, vista_open


def forest_edge_atlas(*,cache_dir=DATA,output_path=None):
    cache_dir=Path(cache_dir)
    pines = sorted(cache_dir.glob('PH_pine_0*_impostor_0.png'))
    shrubs = sorted(cache_dir.glob('PH_shrub_canopy_impostor_*.png'))
    if len(pines)<3 or len(shrubs)!=4:
        raise ValueError('Build the CC0 pine and shrub impostors before the forest-edge atlas')
    def crop(path, crown=False):
        with Image.open(path) as source:rgba=source.convert('RGBA')
        box=rgba.getchannel('A').getbbox()
        if box is None:raise ValueError('Empty source foliage')
        x0,y0,x1,y1=box
        if crown:y1=y0+int((y1-y0)*.68)
        return rgba.crop((x0,y0,x1,y1))
    crowns=[crop(p,True) for p in pines]
    bushes=[crop(p) for p in shrubs]
    atlas=Image.new('RGBA',(1024,1024))
    rng=np.random.default_rng(24026)
    metrics=[]
    for variant in range(4):
        tile=Image.new('RGBA',(512,512))
        low=True
        positions=((12,130),(245,100),(125,12)) if low else ((12,90),(240,115),(130,20),(40,220),(225,230))
        sources=bushes if low else crowns
        for layer,(x,y) in enumerate(positions):
            foliage=sources[(variant+layer)%len(sources)].copy()
            if (variant+layer)%2:foliage=foliage.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            size=(int(rng.integers(235,260)),int(rng.integers(360,435) if low else rng.integers(320,395)))
            foliage=foliage.resize(size,Image.Resampling.LANCZOS)
            tile.alpha_composite(foliage,(x,y+int(rng.integers(-8,9))))
        pixels=np.asarray(tile).copy()
        yy,xx=np.mgrid[:512,:512]
        border=np.minimum.reduce([xx,yy,511-xx,511-yy])
        pixels[:,:,3]=np.uint8(pixels[:,:,3]*np.clip((border-8)/28,0,1))
        if not low:pixels[:,:,:3]=np.uint8(np.clip(pixels[:,:,:3]*[.82,1.04,.82],0,255))
        tile=Image.fromarray(pixels)
        metrics.append(foliage_image_metrics(tile))
        atlas.paste(tile,((variant%2)*512,(variant//2)*512))
    path=Path(output_path) if output_path is not None else cache_dir/'forest_edge_atlas.png'
    path.parent.mkdir(parents=True,exist_ok=True);atlas.save(path)
    return path,dict(sources=[p.name for p in shrubs],variants=4,size=[1024,1024],
                    tiles=metrics,source_license='CC0-1.0',
                    method='Full small-leaf shrubs at realistic scale; individual pine impostors form the separate background')
