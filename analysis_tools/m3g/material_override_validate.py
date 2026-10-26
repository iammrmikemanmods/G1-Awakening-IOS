#!/usr/bin/env python3
"""Compare the native material helper to independent original/corpus records.

The expected branch results come from unchanged original instructions, not the
native implementation. The expected pixels come from the original full PNG
decoder. This script also checks identity metadata against reference.py.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess


def digest(data):
    return hashlib.sha256(data).hexdigest()


def module(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ("probe","archive","manifest","extracted","attachment-report","material-report","png-report","fixture","output"):
        ap.add_argument("--"+name,type=Path,required=True)
    args=ap.parse_args();here=Path(__file__).resolve().parent
    ref=module("material_validate_reference",here/"reference.py")
    attachment=module("material_validate_attachment",here/"model_attachment_oracle.py")
    materials=json.loads(args.material_report.read_bytes());pngs=json.loads(args.png_report.read_bytes())
    attachments=json.loads(args.attachment_report.read_bytes())
    expected_sha="0d510516fe3676ee4a0f4dff60ba64e1c5bf79a0c9800f420b1bbdb1c12febfd"
    if materials["original_sha256"]!=expected_sha or pngs["original_sha256"]!=expected_sha or attachments["original_image_sha256"]!=expected_sha:
        raise ValueError("original reference input identity differs")
    if materials["synthetic_cases"]!=40 or materials["authored_models"]!=7 or materials["authored_steps"]!=11 or pngs["resource_count"]!=11:
        raise ValueError("original reference coverage is incomplete")
    manifest=json.loads(args.manifest.read_bytes())["resources"]
    probe=args.probe.resolve();assets=[];checks=0;object_count=0
    model_results={r["effective_type"]:r for r in materials["actual"]}
    for typ,asset in enumerate(attachments["assets"]):
        rid=asset["resource_id"]
        matches=[r for r in manifest if r["resource_id"]==rid and r["kind"]=="m3g"]
        if len(matches)!=1:raise ValueError("model resource missing/ambiguous")
        row=matches[0];path=args.extracted/"m3g"/row["extracted_filename"];data=path.read_bytes()
        if digest(data)!=row["sha256"] or digest(data)!=asset["payload_sha256"]:
            raise ValueError("asset input identity differs")
        parsed=ref.parse(data);root=asset["model_child"]
        effective=typ if typ<24 else 0
        call=subprocess.run([str(probe),str(path),str(root),str(effective)],capture_output=True,check=True)
        native=json.loads(call.stdout)
        expected=[]
        for obj in parsed[1:]:
            expected.append(dict(index=obj["index"],type=obj["type"],user_id=obj.get("user_id",0),
                references=attachment.references(obj),children=obj.get("children",[]),texture_units=obj.get("textures",[]),
                submesh_appearances=[pair[1] for pair in obj.get("submeshes",[])],
                texture_image=obj.get("image",0) if obj["type"]==17 else 0))
        if len(native["objects"])!=len(expected):raise RuntimeError("identity object count differs")
        for original,decoded in zip(expected,native["objects"]):
            original["references"]=sorted(set(original["references"]))
            decoded["references"]=sorted(set(decoded["references"]))
            if decoded!=original:raise RuntimeError(f"resource{rid} object{original['index']} identity differs")
            checks+=len(original);object_count+=1
        expected_steps=model_results[typ]["original"]["steps"] if typ in model_results else []
        if native["steps"]!=expected_steps:raise RuntimeError(f"resource{rid} native material plan differs from original")
        checks+=1+7*len(expected_steps)
        assets.append(dict(resource_id=rid,effective_type=effective,root=root,payload_sha256=digest(data),
                           objects=len(expected),steps=native["steps"],all_identity_fields_equal=True))
    images=[]
    for original in pngs["results"]:
        rid=original["resource_id"]
        row=next(r for r in manifest if r["resource_id"]==rid and r["kind"]=="png")
        path=args.extracted/"png"/row["extracted_filename"]
        output=subprocess.run([str(probe),"--image",str(rid),str(path)],capture_output=True,check=True).stdout
        header,pixels=output.split(b"\n",1);decoded=json.loads(header)
        if decoded!={k:original[k] for k in ("resource_id","format","width","height","rgba_bytes")}:
            raise RuntimeError("native material image metadata differs")
        if len(pixels)!=original["rgba_bytes"] or digest(pixels)!=original["rgba_sha256"]:
            raise RuntimeError(f"resource{rid} native pixels differ from full original PNG decoder")
        from_archive=subprocess.run([str(probe),"--archive-image",str(rid),str(args.archive)],capture_output=True,check=True).stdout
        if from_archive!=output:raise RuntimeError("archive image identity or output differs from direct resource")
        checks+=8
        images.append(dict(**decoded,png_sha256=original["png_sha256"],rgba_sha256=digest(pixels),
                           rgba_sha256_equal=True,archive_load_exact=True))
    # Only synthetic graphs and original function outputs are committed here.
    fixture=[f"G1_M3G_MATERIAL_V1 {len(materials['synthetic'])}"]
    for case in materials["synthetic"]:
        source,original=case["input"],case["original"]
        fixture.append(f"CASE {source['name']} {source['type']} {source['root']} {len(source['objects'])} {int(original['status']=='rejected')} {len(original['steps'])}")
        for obj in source["objects"]:
            fields=["O",str(obj["index"]),str(obj["type"]),str(obj["user_id"]),str(obj["texture_image"])]
            for key in ("references","children","texture_units","submesh_appearances"):
                fields.extend([str(len(obj[key]))]+[str(x) for x in obj[key]])
            fixture.append(" ".join(fields))
        for step in original["steps"]:
            fixture.append("S "+" ".join(str(int(step[k] or 0)) for k in (
                "slot","resource_id","named_object","appearance_object","texture_object","authored_image_object","used_mesh_fallback")))
        fixture.append("END")
    args.fixture.parent.mkdir(parents=True,exist_ok=True)
    args.fixture.write_text("\n".join(fixture)+"\n")
    report=dict(schema=1,scope="Native source-only material identity/binding/pixel parity; no GPU",
        original_sha256=expected_sha,native_probe_sha256=digest(probe.read_bytes()),
        validator_sha256=digest(Path(__file__).read_bytes()),reader_sha256=digest((here/"reference.py").read_bytes()),
        original_material_report_sha256=digest(args.material_report.read_bytes()),
        original_png_report_sha256=digest(args.png_report.read_bytes()),
        attachment_report_sha256=digest(args.attachment_report.read_bytes()),manifest_sha256=digest(args.manifest.read_bytes()),
        generated_fixture_sha256=digest(args.fixture.read_bytes()),archive_sha256=digest(args.archive.read_bytes()),
        asset_count=len(assets),identity_objects=object_count,
        authored_plans=len(model_results),authored_override_steps=11,image_count=len(images),
        decoded_rgba_bytes=sum(x["rgba_bytes"] for x in images),comparisons=checks,
        assets=assets,images=images,all_passed=True,gpu_tested=False,device_tested=False)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:report[k] for k in ("asset_count","identity_objects","authored_override_steps","image_count","decoded_rgba_bytes","comparisons","all_passed")}))


if __name__=="__main__":main()
