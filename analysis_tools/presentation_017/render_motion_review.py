#!/usr/bin/env python3
"""CPU inspection of actual original posed M3G triangles; NOT a device capture."""
import argparse,json,hashlib
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont

def render(frame_path:Path,clean_pack:Path|None=None)->Image.Image:
 path=frame_path.parent;s=json.loads(frame_path.read_text());w=s['width'];h=s['height']
 color=np.full((h,w,4),[0.055,0.07,0.10,1.0]);depth=np.full((h,w),np.inf)
 textures={}
 for i in s['images']:
  raw=(path/f"image_{i['id']}.rgba").read_bytes()
  override=clean_pack/f"material_{i['width']}x{i['height']}_{hashlib.sha256(raw).hexdigest()}.png" if clean_pack else None
  textures[i['id']]=np.asarray(Image.open(override).convert('RGBA'))/255 if override and override.exists() else np.frombuffer(raw,np.uint8).reshape(i['height'],i['width'],4)/255

 for k,d in enumerate(s['draws']):
  vertices=np.fromfile(path/f"surface_{d['geometry']}.f32",dtype='<f4').reshape(-1,16).astype(float)
  mat=np.array(d['matrix']).reshape(4,4).T;clip=vertices[:,:4]@mat.T
  points=np.stack(((clip[:,0]/clip[:,3]*.5+.5)*w,(.5-clip[:,1]/clip[:,3]*.5)*h),axis=1)
  for i in range(0,len(vertices),3):
   p=points[i:i+3];v=vertices[i:i+3];z=clip[i:i+3,2]/clip[i:i+3,3]
   a=np.floor(p.min(axis=0)).astype(int);b=np.ceil(p.max(axis=0)).astype(int)
   x0,y0=np.maximum(a,[0,0]);x1,y1=np.minimum(b,[w,h])
   if x1<=x0 or y1<=y0:continue
   det=(p[1,1]-p[2,1])*(p[0,0]-p[2,0])+(p[2,0]-p[1,0])*(p[0,1]-p[2,1])
   if abs(det)<1e-9:continue
   front=(det<0) if d['winding']==168 else (det>0)
   if (d['cull']==160 and not front) or (d['cull']==161 and front):continue
   yy,xx=np.mgrid[y0:y1,x0:x1];xf=xx+.5;yf=yy+.5
   u=((p[1,1]-p[2,1])*(xf-p[2,0])+(p[2,0]-p[1,0])*(yf-p[2,1]))/det
   v1=((p[2,1]-p[0,1])*(xf-p[2,0])+(p[0,0]-p[2,0])*(yf-p[2,1]))/det
   v2=1-u-v1;inside=(u>=0)&(v1>=0)&(v2>=0)
   if not inside.any():continue
   ix=xx[inside];iy=yy[inside];bc=np.stack((u[inside],v1[inside],v2[inside]),1);zz=bc@z
   keep=(zz>=0)&(zz<=1)&(zz<=depth[iy,ix]);ix=ix[keep];iy=iy[keep];bc=bc[keep];zz=zz[keep]
   if not len(ix):continue
   if d.get('role',0):
    bayer=np.array([0,8,2,10,12,4,14,6,3,11,1,9,15,7,13,5])
    cut=(bayer[(iy&3)*4+(ix&3)]+.5)/16
    mask=cut<d['mix'] if d['role']==2 else cut>=d['mix']
    ix=ix[mask];iy=iy[mask];bc=bc[mask];zz=zz[mask]
   if not len(ix):continue
   rgba=bc@v[:,8:12];rgba[:,3]*=d['alpha']
   if d['texture']:
    t=d['texture'];uvh=bc@v[:,12:16];uv=uvh[:,:2]/uvh[:,3,None];img=textures[t['image']]
    for axis,name in [(0,'wrap_s'),(1,'wrap_t')]:
     uv[:,axis]=uv[:,axis]%1 if t[name]==241 else np.clip(uv[:,axis],0,1)
    # Pixel-centred bilinear sampling, same policy as the Modern GPU path.
    xy=uv*np.array([img.shape[1],img.shape[0]])-.5
    ij=np.floor(xy).astype(int);fr=xy-ij
    tex=np.zeros((len(ix),4))
    for dy in (0,1):
     for dx in (0,1):
      tx=ij[:,0]+dx;ty=ij[:,1]+dy
      tx=tx%img.shape[1] if t['wrap_s']==241 else np.clip(tx,0,img.shape[1]-1)
      ty=ty%img.shape[0] if t['wrap_t']==241 else np.clip(ty,0,img.shape[0]-1)
      weight=(fr[:,0] if dx else 1-fr[:,0])*(fr[:,1] if dy else 1-fr[:,1])
      tex+=img[ty,tx]*weight[:,None]
    if t['function']==228:rgba=tex.copy()
    else:rgba*=tex
   if d.get('role',0):rgba[:,:3]=rgba[:,:3]*(1-d['highlight'])+np.array([.65,.88,1])*d['highlight']
   alpha=np.clip(rgba[:,3],0,1);nonzero=alpha>0;ix=ix[nonzero];iy=iy[nonzero];zz=zz[nonzero];rgba=rgba[nonzero];alpha=alpha[nonzero,None]
   color[iy,ix,:3]=rgba[:,:3]*alpha+color[iy,ix,:3]*(1-alpha);depth[iy,ix]=zz
 return Image.fromarray(np.uint8(np.clip(color,0,1)*255),'RGBA').convert('RGB')


def render_job(job):
 frame,pack,dest=job;im=render(frame,pack);im.save(dest);return str(dest)
if __name__=='__main__':
 import concurrent.futures
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('pack',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
 a.output.mkdir(exist_ok=True,parents=True);jobs=[]
 for t in (0,11,19):
  for f in sorted((a.root/str(t)).glob('*.json')):
   jobs.append((f,a.pack,a.output/f'{t}_{f.stem}.png'))
 with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
  for result in pool.map(render_job,jobs):print(result,flush=True)
