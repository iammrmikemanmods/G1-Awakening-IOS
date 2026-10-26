#!/usr/bin/env python3
"""Record both original model-material override branches with explicit graphs.

The unchanged caller range 0x3e7e6..0x3f560 runs with its documented stack
frame seeded. The actual Texture2D SetImage wrapper and core execute. Public
Object3D find/query/getter boundaries use supplied graph data; this deliberately
does not claim the complete Object3D reference traversal or resource loading.
"""
import argparse
from collections import Counter
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys


def digest(data):
    return hashlib.sha256(data).hexdigest()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def row(index, typ, user_id=0, references=(), children=(), textures=(), appearances=(), image=0):
    return dict(index=index, type=typ, user_id=user_id, references=list(references),
                children=list(children), texture_units=list(textures),
                submesh_appearances=list(appearances), texture_image=image)


def simple_graph():
    return [row(1, 9, references=[2], children=[2]),
            row(2, 9, references=[3], children=[3]),
            row(3, 14, references=[4, 7], appearances=[4, 7]),
            row(4, 3, 500033589, references=[5], textures=[5]),
            row(5, 17, references=[6], image=6), row(6, 10),
            row(7, 3, 253263228, references=[8], textures=[8]),
            row(8, 17, references=[9], image=9), row(9, 10)]


def synthetic_cases():
    result = [dict(name=f"table_type_{typ}", type=typ, root=1, objects=simple_graph()) for typ in range(24)]
    def add(name, change, typ=3):
        graph=simple_graph();change(graph)
        result.append(dict(name=name, type=typ, root=1, objects=graph))
    add("both_names_absent_shared_last_write", lambda g: [g[i].update(user_id=0) for i in (3,6)])
    add("material2_absent_overwrites_first_texture", lambda g: g[6].update(user_id=0))
    add("named_nonappearance_falls_back", lambda g: (g[3].update(user_id=0),g[5].update(user_id=500033589)))
    add("named_appearance_without_texture0", lambda g: g[3].update(texture_units=[], references=[]))
    add("named_only_texture1_is_not_texture0", lambda g: g[3].update(texture_units=[0,5], references=[0,5]))
    add("different_appearances_share_texture", lambda g: g[6].update(texture_units=[5],references=[5]))
    def unnamed(g):
        g[3]["user_id"]=g[6]["user_id"]=0
    def nested(g):
        unnamed(g);g[1].update(children=[10],references=[10]);g.append(row(10,9,references=[3],children=[3]))
    add("fallback_nested_first_child_chain", nested)
    def skip_empty(g):
        unnamed(g);g[0].update(children=[10,2],references=[10,2]);g.append(row(10,9))
    add("fallback_skips_empty_direct_group", skip_empty)
    def skip_light(g):
        unnamed(g);g[0].update(children=[10,2],references=[10,2]);g.append(row(10,12))
    add("fallback_skips_nongroup_direct_child", skip_light)
    def first_nonmesh(g):
        unnamed(g);g[0].update(children=[10,2],references=[10,2]);g.extend([
            row(10,9,references=[11],children=[11]),row(11,12)])
    add("fallback_nonmesh_first_child_tries_next_group", first_nonmesh)
    def ignore_sibling(g):
        unnamed(g);g[1].update(children=[10,3],references=[10,3]);g.append(row(10,12))
    add("fallback_does_not_search_second_child", ignore_sibling)
    def nested_empty(g):
        unnamed(g);g[1].update(children=[10,3],references=[10,3]);g.append(row(10,9))
    add("fallback_nested_empty_group_is_error", nested_empty)
    def direct_mesh(g):
        unnamed(g);g[0].update(children=[3],references=[3]);g[1].update(children=[],references=[])
    add("fallback_direct_mesh_is_not_searched", direct_mesh)
    add("fallback_null_appearance0_is_error", lambda g: (unnamed(g),g[2].update(submesh_appearances=[0,7],references=[0,7])))
    add("fallback_no_submeshes_is_error", lambda g: (unnamed(g),g[2].update(submesh_appearances=[],references=[])))
    add("world_is_group_interface", lambda g: g[0].update(type=22))
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ("image", "libgcc", "manifest", "extracted", "unicorn-path", "output"):
        ap.add_argument("--"+name, type=Path, required=True)
    args=ap.parse_args();sys.path.insert(0,str(args.unicorn_path))
    import unicorn
    here=Path(__file__).resolve().parent
    base_path=here.parent/"sprite"/"render_oracle.py"
    base=module("material_original_base",base_path)
    ref=module("material_reference",here/"reference.py")
    attachment=module("material_attachment_reference",here/"model_attachment_oracle.py")
    image,gcc=args.image.read_bytes(),args.libgcc.read_bytes()
    if digest(image)!=base.IMAGE_SHA or digest(gcc)!=base.LIBGCC_SHA:
        raise ValueError("original input identity differs")
    resource_pairs=[list(pair) for pair in zip(*[iter(struct.unpack_from("<48i",image,0xceb14-0x1000))]*2)]
    image_dimensions={}
    manifest=json.loads(args.manifest.read_bytes())["resources"]
    for value in {v for p in resource_pairs for v in p if v>=0}:
        rid=value&0xffffff
        found=[r for r in manifest if r["resource_id"]==rid and r["kind"]=="png"]
        if len(found)!=1:raise ValueError("missing/ambiguous original replacement PNG")
        data=(args.extracted/"png"/found[0]["extracted_filename"]).read_bytes()
        if digest(data)!=found[0]["sha256"]:raise ValueError("PNG manifest identity differs")
        image_dimensions[rid]=struct.unpack_from(">II",data,16)

    class Original(base.OriginalRenderer):
        def __init__(self,case):
            super().__init__(image,gcc)
            self.case=case;self.rows={r["index"]:r for r in case["objects"]}
            self.info={};self.publics={};self.internals={};self.internal_info={}
            self.events=[];self.boundaries=Counter();self.failure=None
            self.texture_before={};self.loaded_images={}
            for item in case["objects"]:
                public=self.object({8:"query",0x28:"find",0x74:"get_texture",0xb8:"child_count",
                                    0xbc:"get_child",0xcc:"get_appearance"})
                self.publics[item["index"]]=public;self.info[public]=item
            for item in case["objects"]:
                if item["type"]==10:
                    self.make_internal_image(self.publics[item["index"]],{"authored_image":item["index"]},256,256)
            for item in case["objects"]:
                if item["type"]==17:
                    public=self.publics[item["index"]];internal=self.alloc(0x60)
                    self.u.mem_write(internal,bytes(range(0x60)))
                    self.word(public+4,internal+4);self.word(self.read_word(public)+0x88,0xb1e3f)
                    self.word(internal+0x30,self.internals[item["texture_image"]])
                    self.internals[item["index"]]=internal
                    self.texture_before[item["index"]]=bytes(self.u.mem_read(internal,0x60))
            for rid,(width,height) in image_dimensions.items():
                public=self.object({8:"query"})
                self.info[public]=dict(index=None,type=10,resource_id=rid)
                self.make_internal_image(public,{"resource_id":rid},width,height)
                self.loaded_images[rid]=public

        def make_internal_image(self,public,identity,width,height):
            internal,table=self.alloc(0x60),self.alloc(0x80)
            self.word(internal,table);self.word(internal+8,100)
            for offset,name in ((0x30,"image_width"),(0x34,"image_height")):
                address=self.next_handler;self.next_handler+=4;self.handlers[address]=name
                self.word(table+offset,address|1)
            self.word(public+4,internal+4)
            self.internal_info[internal]=dict(identity=identity,width=width,height=height)
            if "authored_image" in identity:self.internals[identity["authored_image"]]=internal

        def ret(self,value=0):
            self.u.reg_write(self.ar.UC_ARM_REG_R0,value&0xffffffff)
            self.u.reg_write(self.ar.UC_ARM_REG_PC,self.u.reg_read(self.ar.UC_ARM_REG_LR))

        def stop(self,reason):
            self.failure=reason;self.u.emu_stop()

        def hook(self,u,address,size,user):
            if address in (0x3f83c,0x3f844,0xb1bc6):
                self.stop("original_assert_or_argument_error");return
            if not (address in self.handlers or address in self.math or 0xba000<=address<0xbb000 or
                    address in (0x27350,0x26c2a,0xa772c,0xa774e,0xa77a0,0xb1e3e,0x1f540,0x1f512)):
                return
            ar=self.ar;r0,r1,r2,r3=[u.reg_read(getattr(ar,"UC_ARM_REG_R"+str(i))) for i in range(4)]
            if address==0x26c2a:
                rid=r1&0xffffff
                if r1!=0x3000000|rid or rid not in self.loaded_images:raise RuntimeError("unknown resource load")
                self.events.append(dict(operation="load_image",resource_id=rid));self.ret(self.loaded_images[rid]);return
            if address in (0xa772c,0xa774e,0xa77a0,0xbab1c):
                self.boundaries["nonthrowing_error_frame"]+=1;self.ret();return
            if address==0xbabac:
                for n in range(4096):
                    if u.mem_read(r0+n,1)==b"\0":self.boundaries["strlen"]+=1;self.ret(n);return
                raise RuntimeError("unbounded original material name")
            if address==0xb1e3e:
                self.events.append(dict(operation="set_image",texture_object=self.info[r0]["index"],
                                        resource_id=self.info[r1]["resource_id"]))
                return # Execute the actual wrapper and 0xa62e4 mutation.
            name=self.handlers.get(address)
            if name in ("retain","release"):
                self.boundaries[name]+=1;self.ret();return
            if name=="query":
                typ=self.info[r0]["type"]
                accepted=r1==typ or (r1==9 and typ==22) or (r1==16 and typ==14)
                self.word(r2,r0 if accepted else 0);self.boundaries[name]+=1;self.ret(0 if accepted else 1);return
            if name=="find":
                root=self.info[r0]["index"];pending=[root];seen=set();found=[]
                while pending:
                    index=pending.pop()
                    if index in seen:continue
                    seen.add(index);item=self.rows[index]
                    if item["user_id"]==r1:found.append(index)
                    pending.extend(i for i in item["references"] if i)
                if len(found)>1:raise RuntimeError("explicit find boundary requires unique matching ID")
                index=found[0] if found else None
                self.word(r2,self.publics[index] if index else 0)
                self.events.append(dict(operation="find",root=root,key=r1,object=index));self.ret();return
            if name=="child_count":
                self.word(r1,len(self.info[r0]["children"]));self.boundaries[name]+=1;self.ret();return
            if name in ("get_child","get_texture","get_appearance"):
                field={"get_child":"children","get_texture":"texture_units","get_appearance":"submesh_appearances"}[name]
                values=self.info[r0][field]
                if name=="get_texture":index=values[r1] if r1<len(values) else 0
                elif r1>=len(values):self.stop("public_getter_index_error");return
                else:index=values[r1]
                self.word(r2,self.publics[index] if index else 0)
                self.events.append(dict(operation=name,object=self.info[r0]["index"],slot=r1,result=index or None));self.ret();return
            if name in ("image_width","image_height"):
                self.boundaries[name]+=1;self.ret(self.internal_info[r0]["width" if name=="image_width" else "height"]);return
            if 0xba000<=address<0xbb000 and address not in self.math and address not in (0xba1f8,0xba210,0xba204):
                raise RuntimeError("unexpected original external "+hex(address))
            super().hook(u,address,size,user)

        def run(self):
            frame=0x21fe000;self.u.mem_write(frame,b"\0"*0x300)
            self.word(frame+0xc,self.case["type"])
            root_ref=self.alloc(4);self.word(root_ref,self.publics[self.case["root"]])
            self.word(frame+0xe4,root_ref);self.word(frame+0x30,root_ref)
            for i in range(13):self.u.reg_write(getattr(self.ar,"UC_ARM_REG_R"+str(i)),0)
            self.u.reg_write(self.ar.UC_ARM_REG_CPSR,0x30);self.u.reg_write(self.ar.UC_ARM_REG_SP,frame)
            self.u.reg_write(self.ar.UC_ARM_REG_LR,0x3000001)
            try:
                self.u.emu_start(0x3e7e7,0x3f560,count=500_000,timeout=3_000_000)
            except Exception as error:
                raise RuntimeError(f"{self.case['name']}: {error}; PC={self.u.reg_read(self.ar.UC_ARM_REG_PC):#x} "
                    f"LR={self.u.reg_read(self.ar.UC_ARM_REG_LR):#x}; last events={self.events[-5:]}") from error
            if not self.failure and (self.u.reg_read(self.ar.UC_ARM_REG_PC)!=0x3f560 or self.u.reg_read(self.ar.UC_ARM_REG_SP)!=frame):
                raise RuntimeError("material stage did not finish: PC="+hex(self.u.reg_read(self.ar.UC_ARM_REG_PC)))
            if bytes(self.u.mem_read(0x1000,0xd1000))!=self.original_text:
                raise RuntimeError("original main instructions changed")
            if bytes(self.u.mem_read(0x40000000,0x9000))!=self.thin[:0x9000]:
                raise RuntimeError("original libgcc instructions changed")
            final={}
            for index,before in self.texture_before.items():
                after=bytes(self.u.mem_read(self.internals[index],0x60))
                if before[:0x30]!=after[:0x30] or before[0x34:]!=after[0x34:]:
                    raise RuntimeError("original SetImage changed another Texture2D byte")
                final[index]=self.internal_info[self.read_word(self.internals[index]+0x30)]["identity"]
            steps=[]
            if not self.failure:
                segments=[]
                for event in self.events:
                    if event["operation"]=="find":segments.append([])
                    if segments:segments[-1].append(event)
                for segment in segments:
                    find=segment[0];load=next(x for x in segment if x["operation"]=="load_image")
                    gets=[x for x in segment if x["operation"]=="get_texture"]
                    if not gets:raise RuntimeError("completed material branch made no texture lookup")
                    chosen=gets[-1];texture=chosen["result"]
                    steps.append(dict(slot=0 if find["key"]==500033589 else 1,resource_id=load["resource_id"],
                        named_object=find["object"],appearance_object=chosen["object"],texture_object=texture,
                        authored_image_object=self.rows[texture]["texture_image"] if texture else None,
                        used_mesh_fallback=any(x["operation"]=="get_appearance" for x in segment)))
            return dict(status="rejected" if self.failure else "completed",failure=self.failure,
                        steps=steps,events=self.events,texture_images_after=final,
                        only_texture_image_pointer_changed=True,boundary_calls=dict(self.boundaries))

    cases=synthetic_cases()
    synthetic=[]
    for case in cases:
        result=Original(case).run();synthetic.append(dict(input=case,original=result))
    actual=[]
    model_table=struct.unpack_from("<24I",image,0xceab4-0x1000)
    for typ,pair in enumerate(resource_pairs):
        if all(v<0 for v in pair):continue
        rid=model_table[typ]&0xffffff
        found=[r for r in manifest if r["resource_id"]==rid and r["kind"]=="m3g"]
        if len(found)!=1:raise ValueError("ambiguous model resource")
        data=(args.extracted/"m3g"/found[0]["extracted_filename"]).read_bytes()
        if digest(data)!=found[0]["sha256"]:raise ValueError("model extraction differs")
        parsed=ref.parse(data);worlds=[o for o in parsed[1:] if o["type"]==22]
        if len(worlds)!=1:raise ValueError("authored model does not have single World")
        children=worlds[0]["children"]
        root=children[0] if parsed[children[0]]["type"] in (9,22) else children[1]
        if parsed[root]["type"] not in (9,22):raise ValueError("unsupported selected model Group")
        objects=[]
        for o in parsed[1:]:
            objects.append(row(o["index"],o["type"],o.get("user_id",0),attachment.references(o),
                               o.get("children",()),o.get("textures",()),[p[1] for p in o.get("submeshes",())],
                               o.get("image",0) if o["type"]==17 else 0))
        case=dict(name=f"authored_type_{typ}",type=typ,root=root,objects=objects)
        result=Original(case).run()
        if result["status"]!="completed":raise RuntimeError("authored material path did not complete")
        actual.append(dict(resource_id=rid,effective_type=typ,root=root,payload_sha256=digest(data),original=result))
    report=dict(schema=1,scope="Original caller instruction range with seeded frame; actual SetImage wrapper/core",
        original_sha256=digest(image),libgcc_sha256=digest(gcc),manifest_sha256=digest(args.manifest.read_bytes()),
        oracle_source_sha256=digest(Path(__file__).read_bytes()),reader_sha256=digest((here/"reference.py").read_bytes()),
        base_source_sha256=digest(base_path.read_bytes()),unicorn_version=unicorn.__version__,
        entry="0x3e7e6",stop_before="0x3f560",set_image_wrapper="0xb1e3e",set_image_core="0xa62e4",
        table_address="0xceb14",table_tagged_pairs=resource_pairs,
        original_code_readonly_and_unchanged=True,instruction_patches=0,
        boundaries=["public find with explicit unique reachable match; not full Object3D find ordering",
                    "public query/child/appearance/texture getters with supplied object graph",
                    "resource load returns captured-format image object with original PNG dimensions",
                    "public Image width/height and public ownership",
                    "nonthrowing error frames/setjmp; error calls stopped and recorded",
                    "bounded allocator/free, strlen, Unwind registration"],
        not_established=["complete model constructor/load/cache path", "full Object3D find traversal",
                         "GPU upload/rendering", "device rendering"],
        synthetic_cases=len(synthetic),authored_models=len(actual),authored_steps=sum(len(x["original"]["steps"]) for x in actual),
        synthetic=synthetic,actual=actual)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:report[k] for k in ("synthetic_cases","authored_models","authored_steps")}))


if __name__=="__main__":main()
