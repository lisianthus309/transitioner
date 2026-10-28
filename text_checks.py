"""End-to-end text integrity diagnostics used by the packaged self-test."""
from io import BytesIO
import os
from pathlib import Path
import sys
import tempfile
import zipfile
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from openpyxl import load_workbook
import pytesseract
from ocr import read_cell, workbook


def run_text_checks():
    if getattr(sys, 'frozen', False):
        assert sys.flags.utf8_mode == 1, 'Frozen interpreter is not in UTF-8 mode'
    assert os.environ.get('PYTHONUTF8') == '1'
    for stream in (sys.stdout, sys.stderr):
        if stream is not None:
            assert stream.encoding.lower().replace('-', '') == 'utf8'
    fonts = ([Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/name for name in ['arial.ttf','times.ttf']]
             if os.name == 'nt' else [Path('/usr/share/fonts/truetype/dejavu')/name
                                     for name in ['DejaVuSans.ttf','DejaVuSerif.ttf']])
    codes = ['1','7','17','71','1177','7101','0107']
    checked = 0
    for font_path in fonts:
        for size in (14,24):
            font = ImageFont.truetype(str(font_path),size)
            for expected in codes:
                image = Image.new('L',(120,48),255)
                ImageDraw.Draw(image).text((8,6),expected,font=font,fill=0)
                actual = read_cell(np.array(image),'kor+eng')
                assert actual == expected, (font_path.name,size,expected,actual)
                checked += 1
    values = ['한글 테스트','거래처','서울','1','7','17','71','0017','NA','NULL']
    table = pd.DataFrame([values]);table.attrs['source_name']='한글 문서'
    data = workbook([table])
    with tempfile.TemporaryDirectory(prefix='transitioner_') as folder:
        path = Path(folder)/'한글_숫자_검증.xlsx'
        path.write_bytes(data)
        sheet = load_workbook(path).active
        assert [cell.value for cell in sheet[1]] == values
        assert sheet['A1'].font.name == 'Malgun Gothic'
    with zipfile.ZipFile(BytesIO(data)) as archive:
        archive.read('xl/worksheets/sheet1.xml').decode('utf-8',errors='strict')
    import native_ocr
    from english_case import vocabulary
    assert len(vocabulary())==500 and 'eng_case' in pytesseract.get_languages()
    if os.name=='nt' and getattr(sys,'frozen',False):
        import ctypes,shutil
        assert ctypes.windll.kernel32.GetACP()==65001, 'UTF-8 process manifest is not active'
        old_prefix=os.environ['TESSDATA_PREFIX']
        with tempfile.TemporaryDirectory(prefix='모델_경로_') as folder:
            shutil.copy2(Path(old_prefix)/'eng_best.traineddata',Path(folder)/'eng_best.traineddata')
            os.environ['TESSDATA_PREFIX']=folder
            try:
                assert native_ocr.read(np.array(image),'eng_best',6) is not None
            finally:
                native_ocr.clear_current_thread()
                os.environ['TESSDATA_PREFIX']=old_prefix
        print('PASS: native OCR with Korean model-directory path and UTF-8 process manifest',flush=True)
    print(f'Native OCR engine: {native_ocr.version()}',flush=True)
    print(f'PASS: UTF-8 text IO, {checked} numeric OCR cases (1/7, two fonts/sizes), Korean XLSX values and filename',flush=True)
