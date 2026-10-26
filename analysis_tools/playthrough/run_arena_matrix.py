#!/usr/bin/env python3
"""Exercise five Arena maps, two factions, and two opponent settings from an actual profile."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--profile',required=True,type=Path)
    ap.add_argument('--pilot',required=True,type=Path)
    ap.add_argument('--archive',required=True,type=Path)
    ap.add_argument('--terrain-tables',required=True,type=Path)
    ap.add_argument('--output',required=True,type=Path)
    ap.add_argument('--seconds',default=45,type=int)
    args=ap.parse_args()
    if args.output.exists(): raise SystemExit('Output must not already exist')
    args.output.mkdir(parents=True)
    here=Path(__file__).resolve().parent
    def run(config):
        mission,faction,opponent=config
        out=args.output / f'arena_{mission}_faction_{faction}_opponent_{opponent}'
        cmd=[sys.executable,str(here/'run_mode_probe.py'),'--pilot',str(args.pilot.resolve()),
             '--archive',str(args.archive.resolve()),
             '--terrain-tables',str(args.terrain_tables.resolve()),
             '--profile',str(args.profile.resolve()),'--output',str(out.resolve()),
             '--group','2','--mission',str(mission),'--faction',str(faction),
             '--opponent',str(opponent),'--strategy','native-planner-all',
             '--policy','baseline','--seconds',str(args.seconds),'--human-turns','220']
        child=subprocess.run(cmd,capture_output=True,text=True,timeout=args.seconds+40)
        r=json.loads((out/'result.json').read_text()) if (out/'result.json').exists() else {}
        row={'mission':mission,'faction':faction,'opponent':opponent,'command':cmd,
             'returncode':child.returncode,'stdout':child.stdout,'stderr':child.stderr,
             'outcome':r.get('outcome'),'error':r.get('error'),'ticks':r.get('ticks'),
             'handoffs':r.get('native_handoffs'),'profile':r.get('persisted_profile')}
        print(json.dumps({k:v for k,v in row.items() if k not in ['command','stdout','stderr','handoffs','profile']}),flush=True)
        return row
    configs=[(m,f,o) for m in range(5) for f in range(2) for o in range(2)]
    with ThreadPoolExecutor(max_workers=2) as pool: rows=list(pool.map(run,configs))
    record={'scope':'headless native Arena configuration input matrix',
            'presentation_feedback':'synthetic','device_or_rendered_playthrough':False,
            'profile_flags_forced':False,'rows':rows}
    (args.output/'matrix.json').write_text(json.dumps(record,indent=2)+'\n')
    return 0 if all(r['returncode']==0 for r in rows) else 1

if __name__=='__main__': raise SystemExit(main())
