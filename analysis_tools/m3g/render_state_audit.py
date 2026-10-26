#!/usr/bin/env python3
"""Audit a real rigid subtree's required material paths, without GPU claims."""
import argparse
import hashlib
import json
from pathlib import Path
from reference import parse


def audit(data,user_id):
    objects=parse(data)
    roots=[o['index'] for o in objects[1:] if o.get('user_id')==user_id]
    if len(roots)!=1: raise ValueError('requested user ID is missing or ambiguous')
    stack=[roots[0]]
    visited=set()
    appearance_ids=set()
    surface_count=0
    while stack:
        index=stack.pop()
        if index in visited: raise ValueError('cyclic or multiply-parented subtree')
        visited.add(index)
        obj=objects[index]
        if not obj.get('render_enabled',True): continue
        if obj['type'] in (15,16,18): raise ValueError('nonrigid or Sprite3D path required')
        if obj['type']==14:
            for indices,appearance in obj['submeshes']:
                if indices and appearance:
                    surface_count+=1
                    appearance_ids.add(appearance)
        stack.extend(obj.get('children',[]))
    appearances=[]
    texture_ids=set()
    unsupported=[]
    for index in sorted(appearance_ids):
        a=objects[index]
        compositing=objects[a['compositing']]['compositing_values'] if a['compositing'] else [True,True,True,True,68,0,0,0]
        polygon=objects[a['polygon']]['polygon_values'] if a['polygon'] else [160,165,168,False,False,False]
        row={'object':index,'layer':a['layer'],'material':a['material'],'fog':a['fog'],
             'compositing':compositing,'polygon':polygon,'texture_objects':a['textures']}
        if a['material']: unsupported.append({'appearance':index,'reason':'material lighting'})
        if a['fog']: unsupported.append({'appearance':index,'reason':'fog'})
        if len(a['textures'])>1: unsupported.append({'appearance':index,'reason':'multiple texture units'})
        if compositing[6]!=0 or compositing[7]!=0: unsupported.append({'appearance':index,'reason':'nonzero depth offset'})
        texture_ids.update(i for i in a['textures'] if i)
        appearances.append(row)
    textures=[]
    for index in sorted(texture_ids):
        t=objects[index];image=objects[t['image']]
        function,wrap_s,wrap_t,level_filter,image_filter=t['texture_modes']
        textures.append({'object':index,'image':t['image'],'source_format':image['format'],
            'width':image['width'],'height':image['height'],'function':function,
            'wrap_s':wrap_s,'wrap_t':wrap_t,'level_filter':level_filter,'image_filter':image_filter})
        if level_filter!=208: unsupported.append({'texture':index,'reason':'mipmapped levels'})
        if function==225 and image['format'] not in (99,100):
            unsupported.append({'texture':index,'reason':'undefined DECAL source format'})
    return {'schema':1,'model_sha256':hashlib.sha256(data).hexdigest(),'root_user_id':user_id,
        'root_object':roots[0],'surface_count':surface_count,'appearances':appearances,
        'textures':textures,'unsupported_required_paths':unsupported,
        'gpu_execution':False,'apple_compile':False,
        'scope':'Independent serialized render-state audit, not a draw or image comparison'}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--model',type=Path,required=True)
    p.add_argument('--user-id',type=int,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    result=audit(args.model.read_bytes(),args.user_id)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'surfaces':result['surface_count'],'unsupported':result['unsupported_required_paths'],
                      'apple_compile':False,'gpu_execution':False}))


if __name__=='__main__': main()
