#!/usr/bin/env python3
"""Source-derived colour-region curves. No generative images, external art or fonts.

Trace selected colour boundaries to smoothed SVG paths, rasterize once at the
exact target size, retain the original alpha via a separately reconstructed
silhouette. Large smooth fields (sky) use edge-aware continuous reconstruction
instead of banded vector colour quantization. Input/output manifest binds raw
source RGBA SHA256 and every produced PNG. Requires Pillow, numpy, OpenCV,
CairoSVG; only local, generated SVG strings are passed to the SVG renderer.
"""
import argparse,csv,hashlib,io,json,math
from pathlib import Path
import cv2,numpy as np,cairosvg
from PIL import Image

def rgba_key(a):return hashlib.sha256(a.tobytes()).hexdigest()
def curve_path(points,epsilon):
    pts=cv2.approxPolyDP(points,epsilon,True).reshape(-1,2).astype(float)/2.0+0.25
    if len(pts)<3:return ''
    # Keep intentional mechanical corners, round only the vertices on curves.
    cmds=[f'M{pts[0,0]:.3f},{pts[0,1]:.3f}']
    for i in range(len(pts)):
        a,b=pts[i],pts[(i+1)%len(pts)];prev=pts[i-1];nxt=pts[(i+2)%len(pts)]
        def tangent(v0,v1,v2):
            u=v1-v0;v=v2-v1;den=np.linalg.norm(u)*np.linalg.norm(v)
            if den<1e-7 or np.dot(u,v)/den<0.25:return np.zeros(2)
            t=v2-v0;norm=np.linalg.norm(t)
            return t/norm*min(np.linalg.norm(u),np.linalg.norm(v))*0.18 if norm else np.zeros(2)
        c=a+tangent(prev,a,b);d=b-tangent(a,b,nxt)
        cmds.append(f'C{c[0]:.3f},{c[1]:.3f} {d[0]:.3f},{d[1]:.3f} {b[0]:.3f},{b[1]:.3f}')
    return ' '.join(cmds)+' Z'

def reconstruction(source,scale,role):
    a=np.asarray(source.convert('RGBA'),dtype=np.uint8);h,w=a.shape[:2]
    alpha=a[:,:,3].astype(np.float32)/255
    rgb=a[:,:,:3].copy()
    # Extend nearest opaque colour underneath transparent pixels before tracing.
    if np.any(alpha>0) and np.any(alpha==0):
        from scipy.ndimage import distance_transform_edt
        _,idx=distance_transform_edt(alpha==0,return_indices=True)
        rgb[alpha==0]=rgb[idx[0][alpha==0],idx[1][alpha==0]]
    natural=role in ('environment','terrain')
    rgb=cv2.bilateralFilter(rgb,5,22 if natural else 12,1.2)
    # High-resolution sky/atmosphere fields must not become posterized bands.
    smooth=(role=='environment' and w>=256 and h>=256)
    target=(w*scale,h*scale)
    if smooth:
        prem=rgb.astype(np.float32)*alpha[:,:,None]
        aa=np.clip(cv2.resize(alpha,target,interpolation=cv2.INTER_CUBIC),0,1)
        cc=cv2.resize(prem,target,interpolation=cv2.INTER_CUBIC)
        rgbout=np.clip(cc/np.maximum(aa[:,:,None],1e-6),0,255)
        result=np.dstack((rgbout,aa*255)).round().astype(np.uint8)
        return Image.fromarray(result),'',{'mode':'continuous-gradient','paths':0}
    # Segment by paint hue, not by every luminance step: gradient stripes
    # belong to one material. Neutral bevels retain separate tonal bands.
    hsv=cv2.cvtColor(rgb,cv2.COLOR_RGB2HSV)
    hue=hsv[:,:,0].astype(np.int32);sat=hsv[:,:,1];val=hsv[:,:,2]
    classes=np.where(sat<48,100+val.astype(np.int32)//24,(hue+4)//9%20)
    classes=np.where(val<24,200,classes)
    defs=[];paths=[]
    # Start with continuous source colour so single-pixel logos/details are
    # retained when their region is too small to fit a stable curve.
    base_img=Image.fromarray(np.dstack((rgb,np.full((h,w),255,np.uint8)))).resize(target,Image.Resampling.BICUBIC)
    buffer=io.BytesIO();base_img.save(buffer,format='PNG')
    import base64
    base_png=base64.b64encode(buffer.getvalue()).decode()
    for label in np.unique(classes):
        number,component,stats,_=cv2.connectedComponentsWithStats(np.uint8(classes==label),8)
        for ident in range(1,number):
            area=stats[ident,cv2.CC_STAT_AREA]
            if area<3:continue
            mask=np.uint8(component==ident)*255
            contours,_=cv2.findContours(cv2.resize(mask,(w*2,h*2),interpolation=cv2.INTER_NEAREST),cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
            pieces=[curve_path(c,1.0 if role=='character' else 1.25) for c in contours if cv2.contourArea(c)>=1]
            pieces=[x for x in pieces if x]
            if not pieces:continue
            yy,xx=np.nonzero(mask);values=rgb[yy,xx].astype(float)
            # A colour plane reconstructs source shading without adding grain.
            xy=np.column_stack((xx+.5,yy+.5,np.ones(len(xx))))
            coef=np.linalg.lstsq(xy,values,rcond=None)[0]
            grad=coef[:2].mean(axis=1);length=np.linalg.norm(grad)
            gradient_id='g'+str(len(paths))
            if length>.05 and area>=8:
                direction=grad/length;coords=xy[:,:2]@direction
                low,high=float(coords.min()),float(coords.max());centre=xy[:,:2].mean(axis=0)
                p0=centre+direction*(low-centre@direction);p1=centre+direction*(high-centre@direction)
                col0=np.clip(np.r_[p0,1]@coef,0,255).round().astype(int);col1=np.clip(np.r_[p1,1]@coef,0,255).round().astype(int)
                defs.append(f'<linearGradient id="{gradient_id}" gradientUnits="userSpaceOnUse" x1="{p0[0]:.3f}" y1="{p0[1]:.3f}" x2="{p1[0]:.3f}" y2="{p1[1]:.3f}"><stop stop-color="rgb({col0[0]},{col0[1]},{col0[2]})"/><stop offset="1" stop-color="rgb({col1[0]},{col1[1]},{col1[2]})"/></linearGradient>')
                paint=f'url(#{gradient_id})'
            else:
                color=np.median(values,axis=0).round().astype(int);paint=f'rgb({color[0]},{color[1]},{color[2]})'
            paths.append(f'<path fill="{paint}" stroke="{paint}" stroke-width="0.35" stroke-linejoin="round" fill-rule="evenodd" d="{" ".join(pieces)}"/>')
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}"><defs>'+''.join(defs)+f'</defs><image width="{w}" height="{h}" href="data:image/png;base64,{base_png}"/>'+''.join(paths)+'</svg>'
    raster=Image.open(io.BytesIO(cairosvg.svg2png(bytestring=svg.encode(),output_width=target[0],output_height=target[1]))).convert('RGBA')
    out=np.array(raster)
    aa=np.clip(cv2.resize(alpha,target,interpolation=cv2.INTER_CUBIC),0,1)
    if np.all((a[:,:,3]==0)|(a[:,:,3]==255)) and np.any(a[:,:,3]==0):
        contours,_=cv2.findContours(cv2.resize(np.uint8(alpha>0)*255,(w*2,h*2),interpolation=cv2.INTER_NEAREST),cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
        silhouette=' '.join(curve_path(c,1.0) for c in contours if cv2.contourArea(c)>=1)
        masksvg=f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}"><path fill="white" stroke="white" stroke-width="0.35" fill-rule="evenodd" d="{silhouette}"/></svg>'
        cover=Image.open(io.BytesIO(cairosvg.svg2png(bytestring=masksvg.encode(),output_width=target[0],output_height=target[1]))).convert('RGBA')
        aa=np.asarray(cover)[:,:,3].astype(float)/255
    out[:,:,3]=np.rint(aa*255).astype(np.uint8);out[out[:,:,3]==0,:3]=0
    return Image.fromarray(out),svg,{'mode':'colour-region-svg','paths':len(paths)}

def run(inputs:Path,output:Path):
    output.mkdir(parents=True,exist_ok=True);records=[];seen=set()
    script_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    saved=json.loads((output/'manifest.json').read_text()) if (output/'manifest.json').exists() else {}
    old=saved.get('textures',[]) if saved.get('reconstruction_script_sha256')==script_hash else []
    previous={r['key']:r for r in old}
    for row in csv.DictReader((inputs/'inputs.tsv').open(),delimiter='\t'):
        src=Image.open(inputs/(row['name']+'.png')).convert('RGBA');role=row['role'];a=np.asarray(src)
        w,h=src.size;category='ui' if role=='ui' else role if role in ('terrain','sprite') else 'material'
        scale=4 if category in ('ui','terrain','sprite') else 2
        key=f'{category}_{w}x{h}_{rgba_key(a)}'
        dest=output/(key+'.png')
        if key in seen:continue
        seen.add(key)
        if dest.exists() and key in previous and hashlib.sha256(dest.read_bytes()).hexdigest()==previous[key]['output_sha256']:
            records.append(previous[key]);continue
        if role=='sprite':
            # Each original descriptor rectangle is reconstructed separately;
            # geometry/crop offsets remain untouched. No frame-to-frame bleed.
            clean=src.resize((w*scale,h*scale),Image.Resampling.NEAREST)
            rects=json.loads((inputs/(row['name']+'.rects.json')).read_text())
            for x,y,rw,rh in rects:
                tile,_,_=reconstruction(src.crop((x,y,x+rw,y+rh)),scale,'environment')
                clean.paste(tile,(x*scale,y*scale))
            svg='';meta={'mode':'independently-traced-original-rectangles','rectangles':len(rects)}
        elif role=='terrain':
            clean=Image.new('RGBA',(w*scale,h*scale));svgs=[]
            for y in range(0,h,64):
                for x in range(0,w,64):
                    tile,_,meta=reconstruction(src.crop((x,y,x+64,y+64)),scale,role)
                    clean.paste(tile,(x*scale,y*scale))
            svg='';meta={'mode':'independently-traced-64px-cells'}
        else:clean,svg,meta=reconstruction(src,scale,role)
        clean.save(dest)
        # Raw curves are private build intermediates, not shipped font/atlas files.
        records.append({'source':row['name'],'role':role,'key':key,'scale':scale,'width':w,'height':h,
            'source_rgba_sha256':rgba_key(a),'output_sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),**meta})
        print(row['name'],role,meta,flush=True)
    for stale in output.glob('*.png'):
        if stale.stem not in seen:stale.unlink()
    (output/'manifest.json').write_text(json.dumps({'schema':1,'generative_model_used':False,'native_svg_renderer':False,
        'reconstruction_script_sha256':script_hash,'description':'Source-derived contour reconstruction rasterized for existing Metal/UIKit pipeline','textures':records},indent=2)+'\n')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('inputs',type=Path);p.add_argument('output',type=Path);a=p.parse_args();run(a.inputs,a.output)
