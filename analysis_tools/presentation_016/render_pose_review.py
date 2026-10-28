#!/usr/bin/env python3
"""CPU inspection of actual original posed M3G triangles; NOT a device capture."""
import argparse,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont

def render(path:Path)->Image.Image:
 s=json.loads((path/'scene.json').read_text());w=s['width'];h=s['height']
 color=np.full((h,w,4),[0.055,0.07,0.10,1.0]);depth=np.full((h,w),np.inf)
 textures={i['id']:np.frombuffer((path/f"image_{i['id']}.rgba").read_bytes(),np.uint8).reshape(i['height'],i['width'],4)/255 for i in s['images']}
 for k,d in enumerate(s['draws']):
  vertices=np.fromfile(path/f'draw_{k}.f32',dtype='<f4').reshape(-1,16).astype(float)
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
   rgba=bc@v[:,8:12];rgba[:,3]*=d['alpha']
   if d['texture']:
    t=d['texture'];uvh=bc@v[:,12:16];uv=uvh[:,:2]/uvh[:,3,None];img=textures[t['image']]
    for axis,name in [(0,'wrap_s'),(1,'wrap_t')]:
     uv[:,axis]=uv[:,axis]%1 if t[name]==241 else np.clip(uv[:,axis],0,1)
    tx=np.minimum((uv[:,0]*img.shape[1]).astype(int),img.shape[1]-1);ty=np.minimum((uv[:,1]*img.shape[0]).astype(int),img.shape[0]-1);tex=img[ty,tx]
    if t['function']==228:rgba=tex.copy()
    else:rgba*=tex
   alpha=np.clip(rgba[:,3],0,1);nonzero=alpha>0;ix=ix[nonzero];iy=iy[nonzero];zz=zz[nonzero];rgba=rgba[nonzero];alpha=alpha[nonzero,None]
   color[iy,ix,:3]=rgba[:,:3]*alpha+color[iy,ix,:3]*(1-alpha);depth[iy,ix]=zz
 return Image.fromarray(np.uint8(np.clip(color,0,1)*255),'RGBA').convert('RGB')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('output',type=Path);a=p.parse_args();a.output.mkdir(exist_ok=True,parents=True)
 cases=[(11,0,1,'Bumblebee / robot'),(11,1,1,'Bumblebee / vehicle'),(19,0,1,'Frenzy / robot'),(0,0,1,'Optimus Prime / robot'),(0,1,1,'Optimus Prime / vehicle'),(2,0,1,'Megatron / robot')]
 font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',18)
 sheet=Image.new('RGB',(1440,1090),(17,22,30));d=ImageDraw.Draw(sheet)
 d.text((24,16),'BUILD 016 | Original posed 3D meshes — CPU reference, NOT an iPhone capture',font=font,fill='white')
 for j,(t,f,v,label) in enumerate(cases):
  im=render(a.root/f'type_{t}_form_{f}_facing_{v}');im.save(a.output/f'model_{t}_{f}_{v}.png')
  x=(j%3)*480;y=60+(j//3)*510;sheet.paste(im,(x,y));d.text((x+16,y+480),label,font=font,fill='white')
 sheet.save(a.output/'G1_016_Original_Mesh_Pose_Review.jpg',quality=92)
