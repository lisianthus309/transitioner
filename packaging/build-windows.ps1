$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
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
Invoke-WebRequest 'https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/e12c65a915945e4c28e237a9b52bc4a8f39a0cec/eng.traineddata' -OutFile build-runtime\tesseract\tessdata\eng_best.traineddata
if ((Get-FileHash build-runtime\tesseract\tessdata\eng_best.traineddata -Algorithm SHA256).Hash.ToLower() -ne '8280aed0782fe27257a68ea10fe7ef324ca0f8d85bd2fd145d1c2b560bcb66ba') { throw '영어·숫자 모델 체크섬 불일치' }
Copy-Item learning/models/eng_case.traineddata build-runtime\tesseract\tessdata\eng_case.traineddata
if ((Get-FileHash build-runtime\tesseract\tessdata\eng_case.traineddata -Algorithm SHA256).Hash.ToLower() -ne '424883a235d3bf33fc4accfbbee2f609535da4cc57228ce7f6da173ae6e52fbd') { throw 'English case model checksum mismatch' }
$env:TESSDATA_PREFIX = (Resolve-Path build-runtime\tesseract\tessdata).Path
$env:PATH = "C:\Program Files\Tesseract-OCR;$env:PATH"
$env:TRANSITIONER_OCR_BACKEND = 'native'
& $python validation/native_parity.py
if ($LASTEXITCODE -ne 0) { throw 'Native OCR output parity failed' }
& $python validation/english_case_quality.py
if ($LASTEXITCODE -ne 0) { throw 'English case quality regression' }
& $python validation/excel_screenshot.py
if ($LASTEXITCODE -ne 0) { throw 'Excel screenshot precision regression failed' }
& $python validation/multipage.py
if ($LASTEXITCODE -ne 0) { throw 'Multi-page PDF regression failed' }
& $python -m PyInstaller --noconfirm --clean --onedir --name Transitioner --manifest packaging/windows-app.manifest --python-option 'X utf8' --collect-all streamlit --collect-all altair --collect-all pydeck --collect-all pytesseract --collect-all pymupdf --hidden-import ocr --hidden-import native_ocr --add-data 'learning/english_words_500.txt;learning' --add-data 'app.py;.' --add-data 'ocr.py;.' --add-data 'build-runtime\tesseract;tesseract' launcher.py
if ($LASTEXITCODE -ne 0) { throw 'EXE 빌드 실패' }
# Exercise the bundled engine; a full GUI/OCR acceptance check is still required.
& dist\Transitioner\_internal\tesseract\tesseract.exe --version
if ($LASTEXITCODE -ne 0) { throw '번들 Tesseract 실행 실패' }
& dist\Transitioner\_internal\tesseract\tesseract.exe --tessdata-dir dist\Transitioner\_internal\tesseract\tessdata --list-langs
if ($LASTEXITCODE -ne 0) { throw '언어 데이터 확인 실패' }
& dist\Transitioner\Transitioner.exe --self-test
if ($LASTEXITCODE -ne 0) { throw '번들 한국어 OCR/Excel 검증 실패' }
Copy-Item README.md dist\Transitioner\README.md
New-Item -ItemType Directory -Force dist\Transitioner\Model-Licenses | Out-Null
Copy-Item learning/models/UPSTREAM_LICENSE dist\Transitioner\Model-Licenses\Tesseract-language-model-LICENSE.txt
Copy-Item learning/models/MODEL_CARD.md dist\Transitioner\Model-Licenses\MODEL_CARD.md
Compress-Archive -Path dist\Transitioner -DestinationPath dist\Transitioner-Windows.zip -Force
