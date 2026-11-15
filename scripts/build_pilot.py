"""One entry point for the local summit pilot, including assets, previews and checks."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT.parent
STAGES=('assets','build','audit','before','after','test','validate','package','review')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stages',default=','.join(s for s in STAGES if s!='review'),help='Comma-separated stages; default: all')
    parser.add_argument('--blender',type=Path,default=WORK/'tools/blender-3.6.23-windows-x64/blender.exe')
    args=parser.parse_args();stages=args.stages.split(',')
    if any(stage not in STAGES for stage in stages):parser.error('Unknown stage; use '+','.join(STAGES))
    blender=args.blender.resolve()
    if not blender.is_file():raise FileNotFoundError('Use the verified portable Blender 3.6.23, or pass --blender')
    version=subprocess.check_output([str(blender),'--version'],text=True)
    if not version.startswith('Blender 3.6.'):raise RuntimeError('This KN5 pipeline is verified with Blender 3.6, not 4.x/5.x')
    python=blender.parent/'3.6/python/bin/python.exe'
    logs=ROOT/'data/pilot300';logs.mkdir(parents=True,exist_ok=True)
    def run(name,command):
        print('PILOT_STAGE_START',name,flush=True)
        path=logs/(name+'.log')
        with path.open('w',encoding='utf-8') as output:result=subprocess.run([str(v) for v in command],cwd=ROOT/'scripts',stdout=output,stderr=subprocess.STDOUT)
        if result.returncode:
            print(path.read_text(encoding='utf-8',errors='replace')[-9000:],flush=True)
            raise subprocess.CalledProcessError(result.returncode,command)
        print('PILOT_STAGE_OK',name,flush=True)
    def blend(name,script,job=None):
        command=[blender,'--background','--factory-startup','--disable-autoexec','--python-exit-code','1','--python',script]
        if job:command+=['--',job]
        run(name,command)
    for stage in stages:
        if stage=='assets':
            blend('bake_pine_cards',WORK/'bake_pine_cards.py')
            blend('optimize_pines',WORK/'optimize_pines.py')
        elif stage in ('build','audit','before','after','review'):
            if stage=='build':run('source_baseline',[python,ROOT/'scripts/validate_pilot.py','--refresh-baseline'])
            blend(stage,ROOT/'scripts/blender_pilot.py',stage)
        elif stage=='test':
            blend('blender_regressions',ROOT/'scripts/test_pilot_blender.py')
            scripts=[ROOT/'scripts'/name for name in ('pilot_common.py','pilot_scenery.py','pilot_shrubs.py','pilot_treefx.py','treefx_wire.py','mesh_geometry.py','blender_mesh.py','blender_pilot.py','blender_collision_fix.py','validate_guardrail_collisions.py','validate_pilot.py','test_pilot.py','test_pilot_blender.py','test_guardrail_collision.py','build_pilot.py','package_pilot.py')]
            run('syntax',[python,'-m','py_compile',*scripts,WORK/'bake_pine_cards.py',WORK/'optimize_pines.py'])
            run('unit_tests',[python,'-m','unittest','-v','test_pilot','test_guardrail_collision'])
        elif stage=='validate':run('validate',[python,ROOT/'scripts/validate_pilot.py'])
        elif stage=='package':run('package',[python,ROOT/'scripts/package_pilot.py'])
    print('PILOT_PIPELINE_OK',','.join(stages),flush=True)


if __name__=='__main__':main()
