"""Conservative Pillow-only matte for the flat key requested by profile edits.

Geometry checks reject unreliable masks; identity and hair/glasses still require
vision against 03 on the final composition. No inference service or paid retry.
"""
from statistics import median
from PIL import Image, ImageColor, ImageFilter
from .connectors_images import CHROMA_COLOR

VERSION='profile-chroma-v1'
KEY=ImageColor.getrgb(CHROMA_COLOR)
FRAMING_VERSION='profile-framing-v1'
SPILL_VERSION='profile-spill-v1'


def head_bounds(alpha):
    """Estimate hair-to-neck from the silhouette, never claim facial landmarks."""
    small=alpha.copy();small.thumbnail((512,512),Image.Resampling.NEAREST)
    w,h=small.size;pixels=small.tobytes();rows=[]
    for y in range(h):
        xs=[x for x in range(w) if pixels[y*w+x]>=128]
        rows.append((xs[0],xs[-1]+1) if xs else (0,0))
    occupied=[y for y,(left,right) in enumerate(rows) if right>left]
    if not occupied:raise ValueError('No hay figura opaca para estimar la cabeza')
    top,bottom=occupied[0],occupied[-1]+1;span=bottom-top
    radius=max(1,round(h*.008))
    widths=[right-left for left,right in rows]
    smooth=[median(widths[max(top,y-radius):min(bottom,y+radius+1)]) if top<=y<bottom else 0 for y in range(h)]
    candidates=[]
    for y in range(top+max(radius*3,round(span*.22)),top+round(span*.72)):
        peak=max(smooth[top:y-radius],default=0)
        shoulders=max(smooth[y+radius:min(bottom,y+round(span*.25))],default=0)
        local=smooth[max(top,y-radius*2):min(bottom,y+radius*2+1)]
        if (peak and smooth[y]<=min(local) and smooth[y]<=peak*.82 and shoulders>=peak*1.2
                and .85<=(y-top)/peak<=2):
            candidates.append((smooth[y]/peak,y))
    reason='';method='alpha-neck-minimum'
    if candidates and top>0:
        _,neck=min(candidates)
    else:
        method='alpha-width-fallback'
        reason='La máscara toca el borde superior' if top==0 else 'Sin mínimo de cuello fiable entre cabeza y hombros'
        upper=smooth[top+round(span*.1):top+round(span*.35)]
        # A head is approximately 1.3 times its width; bound the fallback so a
        # flat/occluded silhouette cannot produce an extreme zoom.
        neck=top+round(max(span*.3,min(span*.65,median(upper or [w*.35])*1.3)))
    head_rows=rows[top:neck]
    left=min(l for l,r in head_rows if r>l);right=max(r for l,r in head_rows)
    sx,sy=alpha.width/w,alpha.height/h
    return {'top':top*sy,'neck':neck*sy,'left':left*sx,'right':right*sx,
        'method':method,'fallback_reason':reason}


def frame_portrait(image,size):
    bounds=head_bounds(image.getchannel('A'));height=bounds['neck']-bounds['top']
    scale=size[1]*.58/height
    center=(bounds['left']+bounds['right'])/2
    # Transform directly to the bounded output instead of allocating an enlarged
    # source image. Pillow resamples RGBA with premultiplied alpha.
    left=center-size[0]/(2*scale);top=bounds['top']-size[1]*.09/scale
    out=image.transform(size,Image.Transform.AFFINE,(1/scale,0,left,0,1/scale,top),
        resample=Image.Resampling.BICUBIC)
    visible=out.getchannel('A').point(lambda a:255 if a>=128 else 0).getbbox()
    if visible is None:raise ValueError('El encuadre no contiene una figura visible')
    head_top=visible[1]/size[1]
    head_height=(bounds['neck']-top)*scale/size[1]-head_top
    evidence={'id':'render.framing','kind':'render','version':FRAMING_VERSION,
        'method':bounds['method'],'fallback_reason':bounds['fallback_reason'],
        'source_head_height':height/image.height,'head_height':head_height,'head_top':head_top,
        'eyes_y_estimate':head_top+head_height*.4,'eyes_measured':False,
        'scale':scale,'source_head':bounds,'crop_box':[left,top,left+size[0]/scale,top+size[1]/scale],
        'size_px':list(size),'scope':'Cabeza con pelo hasta cuello estimados por alfa; ojos estimados, no landmarks faciales.'}
    evidence['ok']=.55<=head_height<=.60 and .08<=head_top<=.10
    return out,evidence


def spill_regions(image):
    alpha=image.getchannel('A');inner=alpha.filter(ImageFilter.MinFilter(9))
    for (r,g,b,a),near in zip(image.getdata(),inner.getdata()):
        yield a>=32 and near<250, a>=250 and min(r,g,b)>=100 and max(r,g,b)>=160


def spill_index(image):
    """Cyan excess in uncomposited RGB; the brand background is never spill."""
    totals={name:{'pixels':0,'affected_pixels':0,'sum':0} for name in ('edge','light')}
    for (r,g,b,_),regions in zip(image.getdata(),spill_regions(image)):
        excess=max(0,min(g,b)-r)
        for name,selected in zip(totals,regions):
            if selected:
                row=totals[name];row['pixels']+=1;row['sum']+=excess;row['affected_pixels']+=excess>12
    for row in totals.values():
        count=row['pixels'];row['index']=row.pop('sum')/(255*count) if count else 0
        row['affected_fraction']=row['affected_pixels']/count if count else 0
    return totals


def despill(image):
    before=spill_index(image)
    def clean(metrics):return all(r['index']<=.02 and r['affected_fraction']<=.005 for r in metrics.values())
    corrected=0
    if not clean(before):
        colors=[]
        for (r,g,b,a),(edge,light) in zip(image.getdata(),spill_regions(image)):
            excess=max(0,min(g,b)-r) if edge or light else 0
            corrected+=excess>0
            colors.append((r,g-excess,b-excess,a))
        image=image.copy();image.putdata(colors)
    after=spill_index(image) if corrected else before
    return image,{'id':'render.spill','kind':'render','version':SPILL_VERSION,'ok':clean(after),
        'before':before,'after':after,'corrected_pixels':corrected,
        'thresholds':{'cyan_excess_rgb':12,'index':.02,'affected_fraction':.005},
        'scope':'RGB de la persona antes de componer; borde alfa y zonas claras, sin segmentación semántica de piel/camiseta.'}


def components(mask,value):
    """Component sizes and border contact on a bounded binary mask (4-connected)."""
    w,h=mask.size;pixels=bytearray(mask.tobytes());result=[]
    for start in range(w*h):
        if pixels[start]!=value:continue
        pixels[start]=127;stack=[start];area=0;exterior=False
        while stack:
            p=stack.pop();x=p%w;y=p//w;area+=1
            exterior=exterior or x==0 or x==w-1 or y==0 or y==h-1
            for q in ((p-1 if x else -1),(p+1 if x<w-1 else -1),
                      (p-w if y else -1),(p+w if y<h-1 else -1)):
                if q>=0 and pixels[q]==value:pixels[q]=127;stack.append(q)
        result.append((area,exterior))
    return result


def validate(image):
    alpha=image.getchannel('A');hist=alpha.histogram();total=image.width*image.height
    background=sum(hist[:8]);foreground=sum(hist[128:])
    if alpha.getextrema()!=(0,255) or not .03<=background/total<=.95:
        raise ValueError('Recorte sin máscara fiable: proporción de fondo/figura fuera de rango; regenerar el recorte.')
    small=alpha.copy();small.thumbnail((256,256),Image.Resampling.NEAREST)
    binary=small.point(lambda a:255 if a>=128 else 0)
    figures=components(binary,255);area=sum(n for n,_ in figures)
    if not area or max(n for n,_ in figures)<area*.98:
        raise ValueError('Recorte sin máscara fiable: figura fragmentada o restos de fondo aislados; regenerar el recorte.')
    if any(n>max(12,area*.005) for n,exterior in components(binary,0) if not exterior):
        raise ValueError('Recorte sin máscara fiable: agujeros grandes dentro de la figura; cambiar el color clave o regenerar.')
    w,h=small.size
    border=[small.getpixel((x,y)) for x in range(w) for y in (0,h-1)]
    border += [small.getpixel((x,y)) for y in range(1,h-1) for x in (0,w-1)]
    if sum(a<8 for a in border)<len(border)*.5:
        raise ValueError('Recorte sin máscara fiable: fondo exterior insuficiente; regenerar con margen alrededor de la figura.')
    if sum(hist[8:247])>foreground*.15:
        raise ValueError('Recorte sin máscara fiable: bordes demasiado difusos; regenerar con fondo uniforme y sin sombras.')
    return image


def cutout(image):
    """Tolerance 30–105 RGB levels, green despill and roughly 1–2 px feather."""
    image=image.convert('RGB');alpha=bytearray();colors=bytearray()
    for r,g,b in image.getdata():
        distance=max(abs(r-KEY[0]),abs(g-KEY[1]),abs(b-KEY[2]))
        a=max(0,min(255,round((distance-30)*255/75))) if g-max(r,b)>25 else 255
        alpha.append(a)
        # Unmix the key at fractional pixels before feathering; avoid green halos.
        if a==255:color=(r,g,b)
        elif a:color=tuple(max(0,min(255,round((c*255-k*(255-a))/a))) for c,k in zip((r,g,b),KEY))
        else:color=(0,0,0)
        colors.extend(color)
    matte=Image.frombytes('L',image.size,bytes(alpha))
    near_background=matte.filter(ImageFilter.MinFilter(5))
    residue=0
    for i,(a,near) in enumerate(zip(alpha,near_background.getdata())):
        r,g,b=colors[i*3:i*3+3]
        if near<255 and a:g=min(g,max(r,b))
        if a>=128 and g-max(r,b)>35:residue+=1
        colors[i*3+1]=g
    if residue>max(8,sum(a>=128 for a in alpha)*.002):
        raise ValueError('Recorte sin máscara fiable: color clave en la figura o restos verdes; cambiar el color clave o regenerar.')
    # Feather inward: fully removed background never becomes a dark fringe.
    blurred=matte.filter(ImageFilter.GaussianBlur(.7))
    matte=Image.frombytes('L',image.size,bytes(min(a,b) for a,b in zip(alpha,blurred.getdata())))
    result=Image.frombytes('RGB',image.size,bytes(colors));result.putalpha(matte)
    return validate(result)
