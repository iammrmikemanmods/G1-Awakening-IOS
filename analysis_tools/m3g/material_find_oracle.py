#!/usr/bin/env python3
"""Original Object3D.find through seeded authored model reference structures.

Runs 0x99c90 with original Group, Mesh, Appearance, Texture2D, VertexBuffer and
AnimationTrack reference enumerators. Internal graph fields are seeded from
the independently decoded file; this is not a complete object-loader run.
The seven required models have unique material IDs, so no new duplicate-name
ordering policy is inferred for the native helper.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


def digest(data):return hashlib.sha256(data).hexdigest()


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ("image","libgcc","manifest","extracted","material-report","unicorn-path","output"):
        ap.add_argument("--"+name,type=Path,required=True)
    args=ap.parse_args();sys.path.insert(0,str(args.unicorn_path))
    import unicorn
    here=Path(__file__).resolve().parent;base_path=here.parent/"sprite"/"render_oracle.py"
    base=module("original_material_find_base",base_path);ref=module("material_find_reader",here/"reference.py")
    image,gcc=args.image.read_bytes(),args.libgcc.read_bytes()
    if digest(image)!=base.IMAGE_SHA or digest(gcc)!=base.LIBGCC_SHA:raise ValueError("original input identity differs")
    records=json.loads(args.material_report.read_bytes())["actual"]
    manifest=json.loads(args.manifest.read_bytes())["resources"]
    enumerators={2:0x89420,3:0x89ca4,4:0x8b300,9:0x90108,14:0x97db4,
                 17:0xa6500,18:0xa598c,21:0xa9efc,22:0xaae98}

    class Original(base.OriginalRenderer):
        def __init__(self,objects):
            super().__init__(image,gcc)
            self.objects=objects
            self.ptrs={o["index"]:self.alloc(0x120) for o in objects[2:]}
            self.reverse={p:i for i,p in self.ptrs.items()}
            tables={typ:self.alloc(0x40) for typ in {o["type"] for o in objects[2:]}}
            for typ,table in tables.items():self.word(table+0x14,enumerators.get(typ,0x99e1e)|1)
            for o in objects[2:]:
                p=self.ptrs[o["index"]];typ=o["type"]
                if typ in (15,16):raise ValueError("nonrigid reference layout outside scope")
                if o.get("alignment") and any(o["alignment"][2:]):raise ValueError("nonnull alignment reference outside scope")
                self.word(p,tables[typ]);self.word(p+0xc,o["user_id"])
                if o["animation_tracks"]:
                    vector=self.alloc(16);self.array(vector,o["animation_tracks"]);self.word(p+0x10,vector)
                if typ in (9,22):
                    children=o["children"];self.word(p+0x3c,self.pointer(children[0]) if children else 0)
                    for i,child in enumerate(children):
                        self.word(self.pointer(child)+0x34,p)
                        self.word(self.pointer(child)+0x38,self.pointer(children[i+1]) if i+1<len(children) else 0)
                    if typ==22:
                        self.word(p+0x9c,self.pointer(o["active_camera"]));self.word(p+0xa0,self.pointer(o["background"]))
                elif typ==14:
                    self.word(p+0x9c,self.pointer(o["vertex_buffer"]))
                    self.array(p+0xa0,[pair[0] for pair in o["submeshes"]])
                    self.array(p+0xb0,[pair[1] for pair in o["submeshes"]])
                elif typ==3:
                    values=[o[k] for k in ("compositing","fog","polygon","material")]+o["textures"]
                    if len(values)>6:raise ValueError("appearance exceeds two texture units")
                    for i,value in enumerate(values):self.word(p+0x24+i*4,self.pointer(value))
                elif typ==17:self.word(p+0x30,self.pointer(o["image"]))
                elif typ==21:
                    values=[o[k] for k in ("positions","normals","colors")]+[v["array"] for v in o["texcoords"]]
                    if len(values)>5:raise ValueError("vertex buffer exceeds two texture units")
                    for i,value in enumerate(values):self.word(p+0x28+i*4,self.pointer(value))
                elif typ==2:
                    for i,value in enumerate(o["track"][:2]):self.word(p+0x20+i*4,self.pointer(value))
                elif typ==4:self.word(p+0x24,self.pointer(o["background"][4]))
                elif typ==18:
                    for i,value in enumerate(o["sprite"][:2]):self.word(p+0xac+i*4,self.pointer(value))

        def pointer(self,index):
            if index==0:return 0
            if index not in self.ptrs:raise ValueError("invalid seeded reference")
            return self.ptrs[index]

        def array(self,address,values):
            data=self.alloc(max(4,len(values)*4))
            for i,value in enumerate(values):self.word(data+i*4,self.pointer(value))
            self.word(address+4,data);self.word(address+8,len(values));self.word(address+12,len(values))

        def hook(self,u,address,size,user):
            # Pure original find/enumerators use no host method callbacks.
            if 0xba000<=address<0xbb000:raise RuntimeError("unexpected external during original Object3D.find")

        def find(self,root,key):
            self.call(0x99c90,[self.pointer(root),key])
            result=self.u.reg_read(self.ar.UC_ARM_REG_R0)
            if result!=0 and result not in self.reverse:raise RuntimeError("unknown original find result pointer")
            return self.reverse.get(result)

    results=[]
    for record in records:
        rid=record["resource_id"]
        row=next(r for r in manifest if r["resource_id"]==rid and r["kind"]=="m3g")
        data=(args.extracted/"m3g"/row["extracted_filename"]).read_bytes()
        if digest(data)!=record["payload_sha256"] or digest(data)!=row["sha256"]:raise ValueError("model identity differs")
        objects=ref.parse(data);original=Original(objects);queries=[]
        for slot,key in enumerate((500033589,253263228)):
            result=original.find(record["root"],key)
            expected=[s["named_object"] for s in record["original"]["steps"] if s["slot"]==slot]
            if expected and result!=expected[0]:raise RuntimeError("actual original find differs from supplied unique match")
            queries.append(dict(key=key,original_object=result,
                                type=objects[result]["type"] if result else None,
                                used_override_slot=bool(expected)))
        results.append(dict(resource_id=rid,payload_sha256=digest(data),root=record["root"],queries=queries))
    report=dict(schema=1,scope="Unchanged original Object3D.find and real reference enumerators over seeded authored graph",
        original_sha256=digest(image),libgcc_sha256=digest(gcc),oracle_source_sha256=digest(Path(__file__).read_bytes()),
        reader_sha256=digest((here/"reference.py").read_bytes()),base_source_sha256=digest(base_path.read_bytes()),
        material_report_sha256=digest(args.material_report.read_bytes()),unicorn_version=unicorn.__version__,
        find_entry="0x99c90",enumerator_entries={str(k):hex(v) for k,v in enumerators.items()},base_enumerator="0x99e1e",
        original_code_readonly_and_unchanged=True,instruction_patches=0,find_or_getter_substitutions=0,
        seeded_fields="Object3D IDs/animation references, linked Group children, Mesh arrays, Appearance/Texture/VertexBuffer/track references",
        models=len(results),queries=sum(len(r["queries"]) for r in results),required_matches=11,
        results=results,all_passed=True,
        not_established=["complete original object loading/construction", "arbitrary cyclic or ambiguous-ID native traversal", "GPU/device rendering"])
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:report[k] for k in ("models","queries","required_matches","all_passed")}))


if __name__=="__main__":main()
