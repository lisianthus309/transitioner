"""Compare cached C API recognition against independent CLI runs, case-sensitively."""
from pathlib import Path
import os,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import pytesseract
import native_ocr
from ocr import prepare_cell
font_path=(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts/malgun.ttf' if os.name=='nt'
           else Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'))
font=ImageFont.truetype(str(font_path),24)
cases=['한글','서울','거래처','NULL','REG','Cross','cross','CROSS','0017','7','1','']
count=0
for lang in ['eng_best','kor','kor+eng_best']:
 for psm in [6,7]:
  for text in cases:
   im=Image.new('L',(230,60),255);ImageDraw.Draw(im).text((8,6),text,font=font,fill=0)
   pixels=prepare_cell(np.array(im))
   old=pytesseract.image_to_string(pixels,lang=lang,config=f'--psm {psm}',timeout=30).strip()
   new=native_ocr.read(pixels,lang,psm)
   assert old==new,(lang,psm,text,old,new)
   count+=1
print(f'PASS: {count} exact CLI/native comparisons; native version {native_ocr.version()}')

# TSV text, positions, confidence, types and colored-image processing must also match.
import pandas as pd
from ocr import ocr_data
previous=os.environ.get('TRANSITIONER_OCR_BACKEND')
try:
    for rgb in [False,True]:
        image=Image.new('RGB' if rgb else 'L',(650,180),'white');draw=ImageDraw.Draw(image)
        for y,text in [(10,'Hello WORLD Cross cross'),(60,'한글 테스트 0017 NULL'),(110,'1 7 REG 서울')]:
            draw.text((8,y),text,font=font,fill=(0,120,0) if rgb else 0)
        for lang in ['eng','kor+eng']:
            os.environ['TRANSITIONER_OCR_BACKEND']='subprocess';expected=ocr_data(image,lang)
            os.environ['TRANSITIONER_OCR_BACKEND']='native';actual=ocr_data(image,lang)
            pd.testing.assert_frame_equal(expected,actual)
finally:
    if previous is None:os.environ.pop('TRANSITIONER_OCR_BACKEND',None)
    else:os.environ['TRANSITIONER_OCR_BACKEND']=previous
print('PASS: exact TSV data parity including coordinates, confidence, gray and RGB images')
