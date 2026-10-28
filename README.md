# Transitioner

**Windows 배포판:** [Transitioner-Windows-x64.zip 다운로드](https://github.com/lisianthus309/transitioner/releases/download/v0.1.2/Transitioner-Windows-x64.zip). 전체 압축을 해제한 뒤 `Transitioner.exe`를 실행하세요.

이미지·PDF의 표를 로컬 OCR로 읽고 검토·수정한 뒤 Excel로 저장하는 Streamlit 앱입니다. 파일을 외부 OCR 서비스로 전송하지 않습니다.

## 현재 기능

- 이미지/PDF 여러 개 일괄 처리: 최대 20파일, 파일당 100MB, 전체 200MB, 결과 100페이지.
- PDF/다중 프레임 이미지는 파일당 50페이지. PDF, PNG, JPEG, TIFF, BMP, WebP, GIF 지원.
- 한국어/영어 인식. 디지털 PDF는 내장 텍스트를 우선 보존하고 이미지 PDF는 OCR합니다. 강제 OCR도 선택할 수 있습니다.
- 격자 경계를 기반으로 행/열 분리, 사각형 병합 영역 감지 및 Excel 병합 저장.
- 셀과 병합 범위 수동 수정, 잘못된/겹치는 병합 및 값 유실 방지.
- 파일·페이지별 고유 시트, 숫자의 선행 0 보존, 수식으로 실행되지 않는 텍스트 저장.
- 실패한 파일은 오류를 표시하고 다른 파일을 계속 처리합니다.

## 클라우드 실행

Python 3.12, uv, Tesseract 5가 필요합니다. 현재 머신에는 한국어 best 모델과 영어 모델을 `.local/tessdata`에 준비했습니다.

```bash
cd /workspace/transitioner
UV_CACHE_DIR=/tmp/transitioner-uv uv venv --allow-existing .venv
UV_CACHE_DIR=/tmp/transitioner-uv uv pip install --python .venv/bin/python -r requirements.lock
TESSDATA_PREFIX="$PWD/.local/tessdata" .venv/bin/streamlit run app.py --server.address 0.0.0.0 --server.port 8501 --browser.gatherUsageStats false
```

Ubuntu에서 엔진 설치: `sudo apt-get install tesseract-ocr tesseract-ocr-kor`. 한국어 정확도 검증은 tessdata_best 모델 기준이며 배포/환경 설치 스크립트에 모델 다운로드와 체크섬 검증을 포함했습니다.

## Windows 배포판

[공식 릴리스](https://github.com/lisianthus309/transitioner/releases/tag/v0.1.2)에서 ZIP을 받아 전체 압축을 해제한 뒤 `Transitioner/Transitioner.exe`를 더블클릭하세요. Windows 10/11 x64가 대상이며 Python·Tesseract·한국어/영어 인식 데이터를 포함합니다. EXE만 따로 옮기지 마세요.

실행하면 기본 브라우저에 이 PC의 변환 화면이 열립니다. 종료하려면 실행 콘솔을 닫으세요. 파일을 외부 OCR API로 보내지 않습니다.

GitHub Windows 실행기에서 PyInstaller 빌드, 번들 한국어 OCR, 숫자의 선행 0 보존 및 Excel 저장 자체검사가 통과했습니다. 사용자 PC에서의 GUI 수동 검증은 별도입니다. 릴리스 ZIP을 로그인 없는 요청으로 다운로드하여 HTTP 200, SHA256과 ZIP 무결성을 확인했습니다.

Windows 빌드는 `packaging/build-windows.ps1`, 자동 빌드·배포는 `.github/workflows/windows-build.yml`에 있습니다. 워크플로는 검사 성공 후 GitHub가 자동 발급하는 임시 토큰으로 릴리스에 업로드합니다. 개인 토큰이나 원본 첨부 PDF는 코드·배포판에 포함하지 않습니다.

별도로 Linux에서 조립한 네이티브 GUI 실행기 소스는 `packaging/windows-launcher.c`와 `packaging/portable_bootstrap.py`에 있습니다. 현재 공식 릴리스는 위 Windows PyInstaller 빌드 경로를 사용합니다.

## 검증

[검증 결과](validation/RESULTS.md)에 범위와 수치를 기록했습니다. 원본 파일은 코드/배포 ZIP에 포함하지 않습니다.

```bash
export TESSDATA_PREFIX="$PWD/.local/tessdata"
.venv/bin/python validation/check.py
.venv/bin/python validation/large_app.py
.venv/bin/python validation/batch_app.py
.venv/bin/python validation/real_document.py /path/to/345.pdf
.venv/bin/python validation/native_document.py /path/to/345.pdf
```

생성 테스트 데이터와 결과는 `/tmp/transitioner-validation`, 실제 문서 결과는 `/tmp/transitioner-real-validation`에 저장합니다. 실제 문서 대조 기준은 PDF 내장 텍스트이며 사람이 별도 전사한 정답은 아닙니다.

## 제한

어떤 품질·배치의 표든 완벽하게 복원한다고 보장하지 않습니다. 기울어진 사진, 끊어진 경계, 중첩/여러 독립 표, 격자선 없는 표, 손글씨, 비사각형 병합은 수동 검토가 필요합니다. 격자선 없는 표는 열 간격 추정만 지원하며 병합을 자동 복원하지 않습니다. HEIC/RAW, 암호화 PDF는 지원하지 않습니다.

OCR 띄어쓰기는 원본과 다를 수 있습니다. 긴 표의 각 페이지는 별도 시트이며 자동 연결하지 않습니다. 격자선 기반 처리에서 표 바깥의 문구는 제외될 수 있습니다. 최대 100,000셀 제한은 리소스 보호 기준이며 검증한 크기는 300행×30열입니다. 다중 사용자 인증이나 운영용 작업 큐는 포함하지 않았습니다.

## v0.1.1 텍스트 처리

Windows EXE의 Python UTF-8 모드, 콘솔 입출력, OCR TSV 파서를 UTF-8로 명시했습니다. Excel의 한글 글꼴과 한글 파일명·문자열 저장도 검증합니다. 작은 한국어 혼합 표의 셀은 확대·여백 보정 및 추가 영어 정밀 모델로 읽고, 대형 표는 기존 모델을 유지합니다.

Windows와 Linux에서 두 글꼴·두 크기의 1/7 관련 숫자 28건, 한글 XLSX 저장을 확인했습니다. 새로 보고된 오인식 원본은 아직 없어 해당 사례가 해결됐는지는 미확인입니다. UTF-8은 문자 인코딩이며 숫자 1을 7로 읽는 OCR 오인식 자체를 보장해서 고치지는 않습니다. 원본과 변환 값을 검토하세요.

## v0.1.2 — 엑셀 스크린샷 표

엑셀 오류 표시가 포함된 스크린샷 표에서는 원본 이미지 해상도를 보존하고 셀 모서리 표시를 분리한 뒤 셀별·열별 언어 인식을 적용합니다. `엑셀 셀 표시 자동 보정`은 기본 켜짐이며, 자동 감지된 2,000셀 이하 표에서 정밀 처리합니다. 처리 시간이 늘어날 수 있고, 실제로 의미가 있는 녹색 글자가 있는 문서 등에는 이 옵션을 끄고 결과를 비교하세요. 머리글과 한글·영문 혼합 이름은 원본 대조가 필요합니다.

사용자 제공 두 문서의 정답 셀로 비교했을 때 파일 A 77/164 → 162/164, 파일 B 296/343 → 343/343이었습니다. 이 문서들은 개발 중 살펴본 자료이므로 새로운 문서의 정확도를 보장하지 않습니다. 숫자 모델 추가 학습은 개선 이점이 없어 배포하지 않았으며 원본 문서·정답·체크포인트는 공개하지 않습니다.
