"""A final evaluation on additional fonts, after fixing the case-selection rule."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import native_ocr
from ocr import prepare_cell
from english_case import vocabulary,refine
root=Path('/workspace/english-case-final-test');root.mkdir(exist_ok=True)
rows=[]
for word in sorted(vocabulary()):
 for text in [word,word.upper(),word.title()]:
  for font_path in ['/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf']:
   font=ImageFont.truetype(font_path,20);box=font.getbbox(text);image=Image.new('L',(box[2]-box[0]+24,56),255)
   ImageDraw.Draw(image).text((12-box[0],8-box[1]),text,font=font,fill=0)
   rows.append((text,Path(font_path).name,prepare_cell(np.array(image))))
def task(row):
 expected,font,pixels=row;old,confidence=native_ocr.read(pixels,'eng_best',7,True)
 new=refine(pixels,old,7,confidence,{'eng_best','eng_case'})
 return dict(expected=expected,font=font,baseline=old,selected=new)
with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(task,rows))
summary={'total':len(results),'baseline_exact':sum(r['baseline']==r['expected'] for r in results),'selected_exact':sum(r['selected']==r['expected'] for r in results),'corrected':sum(r['baseline']!=r['expected'] and r['selected']==r['expected'] for r in results),'regressed':sum(r['baseline']==r['expected'] and r['selected']!=r['expected'] for r in results)}
(root/'predictions.json').write_text(json.dumps(results,indent=2));(root/'report.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)
