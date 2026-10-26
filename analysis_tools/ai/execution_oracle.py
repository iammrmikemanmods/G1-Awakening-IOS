#!/usr/bin/env python3
"""Original AI plan-consumer control flow at explicit external action boundaries."""
import argparse, importlib.util, json, sys, hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('ai_reference',HERE/'oracle.py')
ai=importlib.util.module_from_spec(spec);spec.loader.exec_module(ai)
class OriginalExecution(ai.OriginalAI):
    def __init__(self,*args):
        self.events=[]
        super().__init__(*args)
    def hook(self,instance,address,size,data):
        ar=self.ar
        r=[instance.reg_read(getattr(ar,'UC_ARM_REG_R'+str(i))) for i in range(4)]
        if address==0x43abc:
            self.events.append(['transform',self.r8(r[0]+9)])
        if address in (0x56044,0x5494c,0x556a8):
            if address==0x56044:
                self.events.append(['render_transform',r[1],r[2]])
            elif address==0x5494c:
                self.events.append(['phase',r[1],self.r8(r[2]+9)])
            else:
                self.events.append(['upgrade',self.r8(r[1]+9)])
            instance.reg_write(ar.UC_ARM_REG_PC,instance.reg_read(ar.UC_ARM_REG_LR));return
        super().hook(instance,address,size,data)
    def consume(self,action,same,form,move_form,arrival,variant=0):
        case=ai.simple_case()
        case['units'][0]['form']=form
        layouts=[
          [[1,0,[[0,0]]]], [[0,0,[]]], [[0,0,[[0,0],[0,0]]]], [],
          [[0,0,[[0,0]]],[0,0,[]]], [[128,0,[[128,0]]]],
          [[0,0,[[0,1]]],[1,0,[[0,0]]]], [[1,1,[[2,2]]]]]
        case['sites']=[{'owner':-1,'xy':[x,y],'groups':[[{'owner':-1,'link':0,'xy':xy} for xy in items]]}
                       for x,y,items in layouts[variant]]
        self.configure_ai(case)
        actor=self.units[0];plan=self.alloc(0x24)
        self.w32(plan+4,action);self.w32(plan+8,case['units'][1]['type'])
        destination=[case['units'][0]['x'],case['units'][0]['y']] if same else [2,2]
        self.vector(plan+0xc,destination,'i')
        self.w32(plan+0x14,0);self.w32(plan+0x18,0);self.w32(plan+0x1c,0)
        self.w8(plan+0x20,move_form);self.w8(plan+0x21,arrival)
        self.w32(self.map+0x28,-1);self.w32(self.map+0x30,0);self.w32(self.map+0xac,937)
        self.call(0x57ed0,[self.map,actor,plan])
        self.check_text()
        return {'action':action,'same':same,'form':form,'move_form':move_form,'arrival':arrival,
                'destination':destination,'sites':case['sites'],'events':self.events,'form_after':self.r8(actor+0xc),
                'flags':[self.r8(actor+n) for n in (0x2c,0x2d,0x2e)],
                'wait_transform_type':ai.combat.signed(self.r32(self.map+0x28)),
                'delay':ai.combat.signed(self.r32(self.map+0xac))}
def main():
    p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--libgcc',type=Path,required=True);p.add_argument('--unicorn-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();sys.path.insert(0,str(args.unicorn_dir));image=args.binary.read_bytes();gcc=args.libgcc.read_bytes()
    if ai.combat.sha(image)!=ai.combat.IMAGE_SHA or ai.combat.sha(gcc)!=ai.combat.LIBGCC_SHA:raise ValueError('wrong source inputs')
    cases=[]
    for action in range(5):
      for same in (0,1):
       for form in (0,1):
        for move in (0,1):
         for arrival in (0,1):cases.append(OriginalExecution(image,gcc).consume(action,same,form,move,arrival))
    for variant in range(1,8):
      for form in (0,1):
       for move in (0,1):
        for arrival in (0,1):cases.append(OriginalExecution(image,gcc).consume(2,1,form,move,arrival,variant))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps({'cases':cases,'original_text_unchanged':True,'boundaries':{'0x56044':'renderer transform request recorded','0x5494c':'command phase selection recorded; phase setup not executed','0x556a8':'upgrade request recorded; upgrade effects not executed'},'original_sha256':ai.combat.sha(image),'oracle_sha256':ai.combat.sha(Path(__file__).read_bytes())},indent=2)+'\n')
    rows=['G1_AI_EXECUTION_V1']
    for index,c in enumerate(cases):
      row=[index,c['action'],c['same'],c['form'],c['move_form'],c['arrival'],*c['destination'],len(c['sites'])]
      rows.append('C '+' '.join(map(str,row)))
      for site in c['sites']:
       rows.append('S '+' '.join(map(str,[*site['xy'],len(site['groups'])])))
       for group in site['groups']:rows.append('I '+' '.join(map(str,[len(group),*[v for i in group for v in i['xy']]])))
      rows.append('R '+' '.join(map(str,[c['form_after'],*c['flags'],c['wait_transform_type'],c['delay'],len(c['events'])])))
      for event in c['events']:rows.append('E '+' '.join(map(str,event)))
    rows.append('END')
    fixture=HERE.parents[1]/'native/tests/ai_execution_original_vectors.txt'
    fixture.write_text('\n'.join(rows)+'\n')
    print(json.dumps({'cases':len(cases),'fixture_sha256':ai.combat.sha(fixture.read_bytes())}))
if __name__=='__main__':main()
