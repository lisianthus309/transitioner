"""Case-sensitive quality gate on all 500 vocabulary words and distinct fonts."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json,os,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image,ImageDraw,ImageFont
import numpy as np
import native_ocr
from english_case import vocabulary
from ocr import prepare_cell,read_cell
fonts=([Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/f for f in ['arial.ttf','times.ttf']]
       if os.name=='nt' else [Path('/usr/share/fonts/truetype/liberation')/f for f in ['LiberationSans-Regular.ttf','LiberationSerif-Regular.ttf']])
import pytesseract
assert 'eng_case' in pytesseract.get_languages(), 'Trained case model is missing'
words=sorted(vocabulary());assert len(words)==500
jobs=[]
for word in words:
 for expected in [word,word.upper(),word.title()]:
  for path in fonts:
   font=ImageFont.truetype(str(path),19);box=font.getbbox(expected)
   im=Image.new('L',(box[2]-box[0]+24,56),255)
   ImageDraw.Draw(im).text((12-box[0],8-box[1]),expected,font=font,fill=0)
   jobs.append((expected,np.array(im)))
def check(job):
 expected,pixels=job;old=native_ocr.read(prepare_cell(pixels),'eng_best',7)
 new=read_cell(pixels,'eng',7)
 assert old.casefold()==new.casefold(),'Case model changed spelling'
 return dict(expected=expected,baseline=old,selected=new)
with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(check,jobs))
summary={'words':500,'images':len(results),'baseline_exact':sum(r['baseline']==r['expected'] for r in results),'selected_exact':sum(r['selected']==r['expected'] for r in results),'corrected':sum(r['baseline']!=r['expected'] and r['selected']==r['expected'] for r in results),'regressed':sum(r['baseline']==r['expected'] and r['selected']!=r['expected'] for r in results)}
print(json.dumps(summary),flush=True)
assert summary['regressed']==0, 'English case quality regression'
assert summary['selected_exact']>=summary['baseline_exact']
print('PASS: 500-word case-sensitive quality gate; no changed spelling or newly wrong cases')
