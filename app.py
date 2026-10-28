import hashlib
import pandas as pd
import pytesseract
import streamlit as st
from ocr import convert, workbook, validate_merges

st.set_page_config(page_title='Transitioner · OCR to Excel', layout='wide')
st.title('이미지·PDF → 엑셀')
st.caption('버전 0.1.3 · 로컬 OCR')
st.write('로컬 OCR로 표를 읽고, 결과를 수정한 뒤 Excel 파일로 저장하세요.')
st.caption('파일은 외부 OCR 서비스로 전송하지 않습니다. 인식 결과는 정확성을 보장하지 않으며 검토가 필요합니다.')
available = set(pytesseract.get_languages())
languages = {'한국어 + 영어': 'kor+eng', '영어': 'eng'}
choice = st.selectbox('인식 언어', list(languages), index=0 if 'kor' in available else 1)
lang = languages[choice]
if 'kor' not in available:
    st.warning('한국어 인식 데이터가 없습니다. README의 설치 절차를 확인하세요.')
uploads = st.file_uploader('이미지·PDF 여러 개 선택 (파일당 최대 100MB)', accept_multiple_files=True, type=['pdf','png','jpg','jpeg','tif','tiff','bmp','webp','gif'])
st.caption('지원 형식: PDF, PNG, JPEG, TIFF, BMP, WebP, GIF. HEIC·RAW 및 손상되거나 암호화된 파일은 지원하지 않습니다.')
force_ocr = st.checkbox('PDF 내장 텍스트 대신 OCR로 강제 인식', value=False)
excel_precision = st.checkbox('엑셀 화면의 셀 표시 자동 보정 (정밀 처리 시 느릴 수 있음)',value=True)
if uploads:
    digest = hashlib.sha256(lang.encode() + str(force_ocr).encode())
    for upload in uploads:
        digest.update(upload.name.encode())
        digest.update(hashlib.sha256(upload.getvalue()).digest())
    if not excel_precision:
        digest.update(b'disable-excel-precision')
    identity = digest.hexdigest()
    if st.session_state.get('identity') != identity:
        st.session_state.pop('results', None)
        st.session_state.identity = identity
    if st.button('표 인식 시작', type='primary'):
        if len(uploads) > 20 or sum(u.size for u in uploads) > 200 * 1024 * 1024:
            st.error('한 번에 20개 파일, 전체 200MB 이하로 선택하세요.')
        elif any(part not in available for part in lang.split('+')):
            st.error('선택한 언어의 OCR 데이터를 먼저 설치하세요.')
        else:
            results = []
            st.session_state.pop('results', None)
            progress = st.progress(0)
            for file_index, upload in enumerate(uploads):
                try:
                    if upload.size > 100 * 1024 * 1024:
                        raise ValueError('파일당 100MB 이하로 선택하세요.')
                    with st.spinner(f'{upload.name} 분석 중…'):
                        file_results = []
                        for page_index, (table,note) in enumerate(convert(upload.getvalue(), upload.name, lang, force_ocr, excel_precision),1):
                            if len(results)+len(file_results) >= 100:
                                raise ValueError('일괄 처리 결과는 최대 100페이지입니다. 파일을 나눠 처리하세요.')
                            table.attrs['source_name'] = f'{upload.name}_p{page_index}'
                            file_results.append((table,note))
                        results.extend(file_results)
                except Exception as exc:
                    st.error(f'{upload.name}: {exc} (이 파일은 결과에서 제외됨)')
                progress.progress((file_index+1)/len(uploads))
            st.session_state.results = results
    if st.session_state.get('results'):
        edited = []
        for index, (table, note) in enumerate(st.session_state.results):
            st.subheader(table.attrs.get('source_name', f'{index+1}페이지'))
            st.caption(note)
            merges = table.attrs.get('merges', [])
            st.caption('병합 범위를 검토·수정하세요. 행/열 번호는 1부터 시작합니다. 병합할 값은 왼쪽 위 셀에 모으세요.')
            ranges = st.data_editor(pd.DataFrame([[r+1,c+1,r1+1,c1+1] for r,c,r1,c1 in merges],
                columns=['시작 행','시작 열','끝 행','끝 열']), num_rows='dynamic', key=f'ranges_{identity}_{index}')
            preserve = st.checkbox('감지된 병합을 Excel에 적용', value=True, key=f'merge_{identity}_{index}')
            result = st.data_editor(table, num_rows='fixed', key=f'{identity}_{index}')
            result.attrs = dict(table.attrs)
            try:
                raw = ranges.to_numpy().tolist() if preserve else []
                if any(any(pd.isna(v) or float(v) != int(v) for v in row) for row in raw):
                    raise ValueError('병합 범위에는 빈칸 없이 정수를 입력하세요.')
                result.attrs['merges'] = [tuple(int(v)-1 for v in row) for row in raw]
                validate_merges(result)
            except (ValueError, TypeError, OverflowError) as exc:
                st.error(str(exc))
                st.stop()
            edited.append(result)
        st.download_button('엑셀 다운로드', workbook(edited), 'converted.xlsx',
                           'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
