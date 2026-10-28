"""Synthetic Excel screenshot regression; contains no uploaded document content."""
from pathlib import Path
import sys,os
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image,ImageDraw,ImageFont
from ocr import recognize
font_path=(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts/arial.ttf' if os.name=='nt'
           else Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
font=ImageFont.truetype(str(font_path),22)
rows,cols,cw,ch,pad=9,3,200,40,20
im=Image.new('RGB',(cols*cw+2*pad,rows*ch+2*pad),'white');d=ImageDraw.Draw(im)
for r in range(rows+1):d.line((pad,pad+r*ch,pad+cols*cw,pad+r*ch),fill='black',width=2)
for c in range(cols+1):d.line((pad+c*cw,pad,pad+c*cw,pad+rows*ch),fill='black',width=2)
expected=[['Code','Flag','Mode']]
for r in range(1,rows):expected.append([f'0017{r:03}', '1' if r%2 else '7','NULL' if r%2 else 'REG'])
for r,row in enumerate(expected):
 for c,text in enumerate(row):
  x,y=pad+c*cw,pad+r*ch
  if r:d.polygon([(x+2,y+2),(x+9,y+2),(x+2,y+9)],fill=(0,128,0))
  d.text((x+5,y+5),text,font=font,fill='black')
table,note=recognize(im,'eng')
assert table.shape==(rows,cols)
assert table.attrs.get('excel_markers_removed',0)>=20
for r in range(rows):
 for c in range(cols):assert ''.join(table.iat[r,c].split())==expected[r][c],(r,c,table.iat[r,c],expected[r][c])
print('PASS: automatic Excel marker detection/removal, per-column language routing, 1/7, leading zeros and NULL')
