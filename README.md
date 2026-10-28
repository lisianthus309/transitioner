# Transitioner

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

`Transitioner-Windows-x64.zip`은 실제 Windows GUI 실행기 `Transitioner.exe`와 Windows용 Python·OCR 엔진·언어 데이터를 포함합니다. ZIP 전체를 압축 해제한 뒤 폴더 안의 EXE를 더블클릭합니다. 별도 Python 설치 없이 실행하도록 구성했습니다. 실행 창을 닫으면 변환 서버와 OCR 프로세스도 종료합니다. Windows 10/11 x64가 대상입니다.

Linux에서 Windows PE 실행기를 크로스 컴파일하고 Windows 전용 패키지와 DLL 구성을 검증했습니다. 실제 Windows에서의 실행 검증은 아직 수행하지 않았습니다. 브라우저를 통해 이 PC의 로컬 변환 화면을 사용하며 파일을 외부 OCR API로 보내지 않습니다.

실행기의 원본은 `packaging/windows-launcher.c`, DLL 초기화 코드는 `packaging/portable_bootstrap.py`입니다. `packaging/verify_portable.py`는 PE 아키텍처, GUI 실행 형식, DLL 포함 여부와 한국어 모델 체크섬을 검사합니다. 실제 Windows 실행 테스트를 대신하지 않습니다.

다른 Windows 빌드 방식으로는 Python 3.12와 Tesseract 5를 설치한 뒤 `packaging/build-windows.ps1`을 실행하는 기존 PyInstaller 경로도 있습니다. 수동 GitHub Actions 구성은 `.github/workflows/windows-build.yml`에 있습니다.

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
