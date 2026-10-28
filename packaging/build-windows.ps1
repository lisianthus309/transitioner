$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
if (-not (Test-Path 'C:\Program Files\Tesseract-OCR\tesseract.exe')) {
    throw 'Tesseract 5를 C:\Program Files\Tesseract-OCR에 설치한 뒤 다시 실행하세요.'
}
python -m venv .build-venv
if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 가상환경 생성 실패' }
$python = '.build-venv\Scripts\python.exe'
& $python -m pip install -r requirements.lock pyinstaller
if ($LASTEXITCODE -ne 0) { throw '의존성 설치 실패' }
New-Item -ItemType Directory -Force build-runtime\tesseract | Out-Null
Copy-Item 'C:\Program Files\Tesseract-OCR\*' build-runtime\tesseract -Recurse -Force
Invoke-WebRequest 'https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/e12c65a915945e4c28e237a9b52bc4a8f39a0cec/kor.traineddata' -OutFile build-runtime\tesseract\tessdata\kor.traineddata
if ((Get-FileHash build-runtime\tesseract\tessdata\kor.traineddata -Algorithm SHA256).Hash.ToLower() -ne 'f888d4038348a0c3d25151e7f452bda0d74ca275b18cab146798bcbb94084fff') { throw '한국어 모델 체크섬 불일치' }
& $python -m PyInstaller --noconfirm --clean --onedir --name Transitioner --collect-all streamlit --collect-all altair --collect-all pydeck --collect-all pytesseract --collect-all pymupdf --hidden-import ocr --add-data 'app.py;.' --add-data 'ocr.py;.' --add-data 'build-runtime\tesseract;tesseract' launcher.py
if ($LASTEXITCODE -ne 0) { throw 'EXE 빌드 실패' }
# Exercise the bundled engine; a full GUI/OCR acceptance check is still required.
& dist\Transitioner\_internal\tesseract\tesseract.exe --version
if ($LASTEXITCODE -ne 0) { throw '번들 Tesseract 실행 실패' }
& dist\Transitioner\_internal\tesseract\tesseract.exe --tessdata-dir dist\Transitioner\_internal\tesseract\tessdata --list-langs
if ($LASTEXITCODE -ne 0) { throw '언어 데이터 확인 실패' }
& dist\Transitioner\Transitioner.exe --self-test
if ($LASTEXITCODE -ne 0) { throw '번들 한국어 OCR/Excel 검증 실패' }
Copy-Item README.md dist\Transitioner\README.md
Compress-Archive -Path dist\Transitioner -DestinationPath dist\Transitioner-Windows.zip -Force
