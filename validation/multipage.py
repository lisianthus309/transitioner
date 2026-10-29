"""Short tables, security margins and all PDF pages, including real app/export."""
from pathlib import Path
from io import BytesIO
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pymupdf as fitz
from openpyxl import load_workbook
from streamlit.testing.v1 import AppTest
from ocr import convert,workbook

doc=fitz.open()
for index in range(3):
 p=doc.new_page(width=600,height=840)
 p.insert_text((20,25),'InternalUseOnly - DO NOT DISTRIBUTE',color=(1,0,0))
 p.insert_text((20,820),'InternalUseOnly - DO NOT DISTRIBUTE',color=(1,0,0))
 for x in [20,280,560]:p.draw_line((x,60),(x,180))
 for y in [60,120,180]:p.draw_line((20,y),(560,y))
 for x,y,v in [(35,90,['ALPHA','BRAVO','CHARLIE'][index]),(300,90,'0017'),(35,150,'Apple'),(300,150,'TOTAL')]:p.insert_text((x,y),v,fontsize=18)
data=doc.tobytes()
for force in [False,True]:
 results=list(convert(data,'multiple.pdf','eng',force))
 assert len(results)==3
 for index,(t,n) in enumerate(results):
  assert t.shape==(2,2),t.shape
  assert t.iat[0,0]==['ALPHA','BRAVO','CHARLIE'][index],t
  assert t.iat[0,1]=='0017',t
  assert not any('Internal' in v or 'DISTRIBUTE' in v for v in t.to_numpy().ravel())
class Upload:
 name='multiple.pdf';size=len(data)
 def getvalue(self):return data
app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'))
with patch('streamlit.file_uploader',return_value=[Upload()]):
 app.run();app.selectbox[0].select('영어').run();app.button[0].click().run(timeout=90)
assert not app.exception
results=app.session_state['results'];assert len(results)==3
book=load_workbook(BytesIO(workbook([t for t,n in results])))
assert len(book.worksheets)==3
for index,s in enumerate(book):assert s['A1'].value==['ALPHA','BRAVO','CHARLIE'][index]
assert any('3페이지' in s.value for s in app.success)
print('PASS: all 3 pages, digital + forced OCR, short tables, excluded red security margins, app results and three distinct Excel sheets')
