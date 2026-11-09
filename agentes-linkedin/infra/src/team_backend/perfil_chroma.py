"""Conservative Pillow-only matte for the flat key requested by profile edits.

Geometry checks reject unreliable masks; identity and hair/glasses still require
vision against 03 on the final composition. No inference service or paid retry.
"""
from PIL import Image, ImageColor, ImageFilter
from .connectors_images import CHROMA_COLOR

VERSION='profile-chroma-v1'
KEY=ImageColor.getrgb(CHROMA_COLOR)


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
