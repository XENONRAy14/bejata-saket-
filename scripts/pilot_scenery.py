"""Deterministic, layered roadside scenery made only from the project's CC0 sources."""
import math

from pilot_common import DATA, Image, np, frame, ground, foliage_image_metrics


def vista_open(station, length, side, sea_side):
    return side == sea_side and .68 * length < station < .83 * length


def edge_layout(data, sea_side):
    rng = np.random.default_rng(24025)
    length = float(data['s3'][-1])
    result = []
    for side in (0, 1):
        for tier, spacing in enumerate((2.8, 4.2)):
            for station in np.arange(3, length - 2, spacing):
                station = float(np.clip(station + rng.uniform(-.3, .3), 2, length - 2))
                if vista_open(station, length, side, sea_side):
                    continue
                width = float(rng.uniform(*((3.5,4.5),(4.8,6.0))[tier]))
                height = float(rng.uniform(*((1.4,1.9),(2.5,3.3))[tier]))
                half_road = float(np.interp(station, data['s3'], data['width'])) / 2
                offset = half_road + (2.5, 6.3)[tier] + width / 2
                _, tangent, _ = frame(data, station)
                result.append(dict(
                    station=station, side=side, tier=tier, offset=offset,
                    position=ground(data, station, side, offset).tolist(),
                    width=width, height=height,
                    angle=math.atan2(tangent[1], tangent[0]) + float(rng.uniform(-.17, .17)),
                    variant=int(rng.integers(4)),
                ))
    return result


def forest_edge_atlas():
    pines = sorted(DATA.glob('PH_pine_0*_impostor_0.png'))
    shrubs = sorted(DATA.glob('PH_shrub_canopy_impostor_*.png'))
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
    path=DATA/'forest_edge_atlas.png';atlas.save(path)
    return path,dict(sources=[p.name for p in shrubs],variants=4,size=[1024,1024],
                    tiles=metrics,source_license='CC0-1.0',
                    method='Full small-leaf shrubs at realistic scale; individual pine impostors form the separate background')
