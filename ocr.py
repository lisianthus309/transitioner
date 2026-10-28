"""Local OCR: ruled table cells first, word alignment otherwise."""
from io import BytesIO
import os
os.environ.setdefault("OMP_THREAD_LIMIT", "1")
import cv2
import numpy as np
import pandas as pd
import pytesseract
from PIL import Image, ImageOps, ImageSequence
import pymupdf as fitz
from openpyxl import Workbook
from openpyxl.styles import Alignment
from openpyxl.utils import get_column_letter


def pages(data, name):
    if data.startswith(b'%PDF'):
        with fitz.open(stream=data, filetype='pdf') as doc:
            if doc.needs_pass:
                raise ValueError('암호가 설정된 PDF는 먼저 암호를 해제하세요.')
            if len(doc) > 50:
                raise ValueError('PDF는 한 번에 50페이지까지 지원합니다.')
            for page in doc:
                scale = 3 if page.rect.width * page.rect.height * 9 <= 65_000_000 else 2
                pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                yield Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    else:
        with Image.open(BytesIO(data)) as img:
            for i, frame in enumerate(ImageSequence.Iterator(img)):
                if i >= 50:
                    raise ValueError('이미지는 한 번에 50프레임까지 지원합니다.')
                yield ImageOps.exif_transpose(frame).convert('RGB')


def _centers(mask, axis, threshold):
    indices = np.where(np.count_nonzero(mask, axis=axis) > threshold)[0]
    if not len(indices):
        return []
    groups = np.split(indices, np.where(np.diff(indices) > 1)[0] + 1)
    return [int(np.mean(group)) for group in groups]


def recognize(image, lang, text_words=None):
    gray = cv2.cvtColor(np.array(image.convert('RGB')), cv2.COLOR_RGB2GRAY)
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY_INV, 31, 15)
    h, w = gray.shape
    horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN,
                                  cv2.getStructuringElement(cv2.MORPH_RECT, (max(20, w//25), 1)))
    vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN,
                                cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(20, h//25))))
    ys = _centers(horizontal, 1, w * .35)
    xs = _centers(vertical, 0, h * .50)
    if len(xs) >= 2 and len(ys) >= 2:
        nr, nc = len(ys)-1, len(xs)-1
        if nr * nc > 100000:
            raise ValueError('100,000셀 이하의 표를 사용하세요.')
        # Missing interior borders connect elementary grid cells. Only rectangular
        # connected components can represent an Excel merged cell.
        parent = list(range(nr*nc))
        def root(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        def join(a, b):
            parent[root(a)] = root(b)
        for r in range(nr):
            for c in range(nc):
                if c+1 < nc:
                    segment = vertical[ys[r]+4:ys[r+1]-3, xs[c+1]-2:xs[c+1]+3]
                    if segment.size and np.mean(np.any(segment > 0, axis=1)) < .25:
                        join(r*nc+c, r*nc+c+1)
                if r+1 < nr:
                    segment = horizontal[ys[r+1]-2:ys[r+1]+3, xs[c]+4:xs[c+1]-3]
                    if segment.size and np.mean(np.any(segment > 0, axis=0)) < .25:
                        join(r*nc+c, (r+1)*nc+c)
        groups = {}
        for r in range(nr):
            for c in range(nc):
                groups.setdefault(root(r*nc+c), []).append((r,c))
        merges, owners, uncertain = [], {}, 0
        for cells in groups.values():
            r0, c0 = min(r for r,c in cells), min(c for r,c in cells)
            r1, c1 = max(r for r,c in cells), max(c for r,c in cells)
            if len(cells) == (r1-r0+1)*(c1-c0+1):
                if len(cells) > 1:
                    merges.append((r0,c0,r1,c1))
                for cell in cells:
                    owners[cell] = (r0,c0)
            else:
                uncertain += 1
                for cell in cells:
                    owners[cell] = cell
        # Remove rules and OCR strips, rather than spawning 9,000 OCR processes.
        clean = gray.copy()
        rules = np.zeros_like(binary)
        for y in ys:
            rules[max(0,y-3):y+4,:] = horizontal[max(0,y-3):y+4,:]
        for x in xs:
            rules[:,max(0,x-3):x+4] |= vertical[:,max(0,x-3):x+4]
        rules = cv2.dilate(rules, np.ones((3,3), np.uint8))
        clean[rules > 0] = 255
        entries = {}
        confidences = []
        # Keep strips bounded while avoiding cuts through cells or vertical merges.
        start = 0
        # Compact forms benefit from isolated fields; tall tables retain column context.
        small_korean = 'kor' in lang and nr <= 20 and nr*nc <= 200 and text_words is None
        while start < nr and not small_korean:
            end = start + 1
            while end < nr and ys[end+1]-ys[start] <= 1600:
                end += 1
            while end < nr and any(r0 < end <= r1 for r0,c0,r1,c1 in merges):
                end += 1
            if text_words is not None:
                end = nr
            top, bottom = (0, ys[end]) if text_words is not None else (ys[start], ys[end])
            if text_words is not None:
                words = pd.DataFrame(text_words)
            else:
                cuts = [0, gray.shape[1]]
                if 'kor' in lang:
                    cuts = [xs[0]] + [xs[c] for c in range(1,nc)
                        if not any(c0 < c <= c1 and r0 < end and r1 >= start
                                   for r0,c0,r1,c1 in merges)] + [xs[-1]]
                chunks = []
                for left,right in zip(cuts,cuts[1:]):
                    chunk = pytesseract.image_to_data(clean[top:bottom, left:right], lang=lang,
                        config='--psm 6', output_type=pytesseract.Output.DATAFRAME,
                        pandas_config={'dtype': {'text': str}}, timeout=180)
                    chunk['left'] += left
                    chunks.append(chunk)
                words = pd.concat(chunks, ignore_index=True)
            words = words.dropna(subset=['text'])
            for word in words.itertuples():
                if word.conf < 0:
                    continue
                x, y = word.left + word.width/2, top + word.top + word.height/2
                c = int(np.searchsorted(xs, x, side='right')-1)
                r = int(np.searchsorted(ys, y, side='right')-1)
                if 0 <= r < nr and 0 <= c < nc:
                    owner = owners[(r,c)]
                    entries.setdefault(owner, []).append((y, word.left, str(word.text), word.height))
                    confidences.append(float(word.conf))
            start = end
        rows = [[''] * nc for _ in range(nr)]
        for (r,c), tokens in entries.items():
            lines = []
            tolerance = max(3, float(np.median([height for y,x,text,height in tokens])) * .65)
            for token in sorted(tokens):
                if not lines or abs(token[0]-np.mean([t[0] for t in lines[-1]])) > tolerance:
                    lines.append([token])
                else:
                    lines[-1].append(token)
            rows[r][c] = '\n'.join(' '.join(t[2] for t in sorted(line, key=lambda t:t[1])) for line in lines)
        if small_korean:
            merge_bounds = {(r0,c0):(r1,c1) for r0,c0,r1,c1 in merges}
            for r,c in sorted(set(owners.values())):
                r1,c1 = merge_bounds.get((r,c),(r,c))
                crop = gray[ys[r]+4:ys[r1+1]-3, xs[c]+4:xs[c1+1]-3]
                if crop.size:
                    crop = cv2.copyMakeBorder(crop,8,8,8,8,cv2.BORDER_CONSTANT,value=255)
                    rows[r][c] = pytesseract.image_to_string(crop,lang=lang,config='--psm 6',timeout=30).strip()
        table = pd.DataFrame(rows)
        table.attrs['text_source'] = 'PDF text layer' if text_words is not None else 'local OCR'
        table.attrs['merges'] = merges
        table.attrs['uncertain_components'] = uncertain
        table.attrs['mean_confidence'] = float(np.mean(confidences)) if confidences else 0
        return table, (f"{table.attrs['text_source']} · 격자 {nr}행 × {nc}열 · 병합 {len(merges)}개 · "
                       f'불규칙 영역 {uncertain}개 (수동 검토 필요). 병합 위치를 아래에서 확인하세요.')
    words = pytesseract.image_to_data(image, lang=lang, config='--psm 6',
                                     output_type=pytesseract.Output.DATAFRAME, pandas_config={'dtype': {'text': str}}, timeout=60)
    words = words.dropna(subset=['text'])
    words = words[words.conf >= 0]
    if words.empty:
        return pd.DataFrame([['']]), '텍스트를 찾지 못했습니다.'
    # Infer column anchors from large gaps between words on each recognized line.
    lines = list(words.groupby(['block_num', 'par_num', 'line_num'], sort=False))
    median_height = float(words.height.median())
    anchors = [int(words.left.min())]
    for _, line in lines:
        previous = None
        for word in line.sort_values('left').itertuples():
            if previous is not None and word.left - previous > median_height * 2:
                if all(abs(word.left - x) > median_height * 2 for x in anchors):
                    anchors.append(int(word.left))
            previous = word.left + word.width
    anchors.sort()
    rows = []
    for _, line in lines:
        row = [''] * len(anchors)
        for word in line.sort_values('left').itertuples():
            col = min(range(len(anchors)), key=lambda j: abs(word.left-anchors[j]))
            row[col] = (row[col] + ' ' + str(word.text)).strip()
        rows.append(row)
    return pd.DataFrame(rows), '격자선 없음: 간격으로 열을 추정했습니다. 행·열을 반드시 검토하세요.'


def validate_merges(table):
    occupied = set()
    for bounds in table.attrs.get('merges', []):
        if len(bounds) != 4 or any(not isinstance(v, (int, np.integer)) for v in bounds):
            raise ValueError('병합 범위는 정수 행·열 번호 4개여야 합니다.')
        r0,c0,r1,c1 = bounds
        if not (0 <= r0 <= r1 < len(table) and 0 <= c0 <= c1 < len(table.columns)):
            raise ValueError('병합 범위가 표를 벗어났습니다.')
        for r in range(r0,r1+1):
            for c in range(c0,c1+1):
                if (r,c) in occupied:
                    raise ValueError('병합 범위가 서로 겹칩니다.')
                occupied.add((r,c))
                value = table.iat[r,c]
                if (r,c) != (r0,c0) and not pd.isna(value) and str(value) != '':
                    raise ValueError('병합으로 값이 사라집니다. 값은 병합 영역의 왼쪽 위 셀로 옮기세요.')


def workbook(tables):
    book = Workbook()
    book.remove(book.active)
    for index, table in enumerate(tables, 1):
        validate_merges(table)
        import re
        title = re.sub(r'[\\/*?:\[\]]', '_', table.attrs.get('source_name', 'Page'))
        sheet = book.create_sheet(f'{index}_{title}'[:31])
        for row in table.fillna('').itertuples(index=False, name=None):
            sheet.append([str(value) for value in row])
        for r0,c0,r1,c1 in table.attrs.get('merges', []):
            if r1 < len(table) and c1 < len(table.columns):
                sheet.merge_cells(start_row=r0+1, start_column=c0+1, end_row=r1+1, end_column=c1+1)
        for row in sheet:
            for cell in row:
                # OCR content is always text, including strings beginning with '='.
                if cell.__class__.__name__ != 'MergedCell':
                    cell.data_type = 's'
                cell.alignment = Alignment(wrap_text=True, vertical='top')
        for column in range(1, len(table.columns)+1):
            sheet.column_dimensions[get_column_letter(column)].width = 24
    output = BytesIO()
    book.save(output)
    return output.getvalue()


def convert(data, name, lang, force_ocr=False):
    """Prefer embedded digital text when present; scanned PDFs use local OCR."""
    if not data.startswith(b'%PDF') or force_ocr:
        for image in pages(data, name):
            yield recognize(image, lang)
        return
    with fitz.open(stream=data, filetype='pdf') as doc:
        if doc.needs_pass or len(doc) > 50:
            raise ValueError('암호 없는 50페이지 이하 PDF를 사용하세요.')
        for page in doc:
            pix = page.get_pixmap(matrix=fitz.Matrix(2,2), alpha=False)
            image = Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
            sx, sy = pix.width/page.rect.width, pix.height/page.rect.height
            words = [dict(left=x0*sx, top=y0*sy, width=(x1-x0)*sx,
                          height=(y1-y0)*sy, text=text, conf=100)
                     for x0,y0,x1,y1,text,*_ in page.get_text('words')]
            if not words:
                scale = 3 if page.rect.width * page.rect.height * 9 <= 65_000_000 else 2
                pix = page.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False)
                image = Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
            yield recognize(image, lang, words if words else None)
