"""Initialize the bundled Windows DLL search paths before importing application libraries."""
import os
import sys

root = os.path.dirname(os.path.abspath(__file__))
runtime = os.path.join(root, 'runtime')
dll_handles = []
if os.name == 'nt':
    for directory in [runtime, os.path.join(runtime,'Library','bin'), os.path.join(runtime,'DLLs')]:
        if os.path.isdir(directory):
            dll_handles.append(os.add_dll_directory(directory))
os.environ['PATH'] = os.pathsep.join([os.path.join(runtime,'Library','bin'),runtime,os.environ.get('PATH','')])
os.environ['TESSDATA_PREFIX'] = os.path.join(runtime,'share','tessdata')
os.environ.setdefault('OMP_THREAD_LIMIT','1')
sys.path.insert(0,root)

from pathlib import Path
import logging
import runpy
import traceback

log_root=Path(os.environ.get('LOCALAPPDATA',os.environ.get('TEMP',root)))/'Transitioner'/'logs'
log_root.mkdir(parents=True,exist_ok=True)
log_file=log_root/f'startup-{os.getpid()}.log'
with log_file.open('w',encoding='utf-8',buffering=1) as output:
    sys.stdout=sys.stderr=output
    print('Transitioner startup',flush=True)
    try:
        runpy.run_path(os.path.join(root,'launcher.py'),run_name='__main__')
    except BaseException:
        traceback.print_exc()
        raise
