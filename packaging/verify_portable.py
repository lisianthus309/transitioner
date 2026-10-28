"""Static Windows distribution checks. This does not execute Windows programs."""
from pathlib import Path
import hashlib
import json
import sys
import pefile

root=Path(sys.argv[1]).resolve()
required=['Transitioner.exe','runtime/pythonw.exe','runtime/python312.dll',
          'runtime/Library/bin/tesseract.exe','runtime/share/tessdata/kor.traineddata',
          'runtime/share/tessdata/eng.traineddata','portable_bootstrap.py','launcher.py','app.py','ocr.py']
assert all((root/p).is_file() for p in required),'Missing runtime file'
exe=pefile.PE(str(root/'Transitioner.exe'))
assert exe.FILE_HEADER.Machine==0x8664 and exe.OPTIONAL_HEADER.Subsystem==2
assert 'portable_bootstrap.py'.encode('utf-16-le') in (root/'Transitioner.exe').read_bytes()
assert hashlib.sha256((root/'runtime/share/tessdata/kor.traineddata').read_bytes()).hexdigest()=='f888d4038348a0c3d25151e7f452bda0d74ca275b18cab146798bcbb94084fff'
# These DLLs are provided by Windows 10/11, not by third-party installers.
os_dlls=set('advapi32 bcrypt crypt32 dbghelp dnsapi gdi32 imm32 iphlpapi kernel32 msvcrt mswsock ncrypt netapi32 ntdll normaliz ole32 oleaut32 psapi rpcrt4 secur32 setupapi shell32 shlwapi user32 userenv ucrtbase version winhttp wininet winmm wldap32 ws2_32 wtsapi32 comdlg32 comctl32 powrprof propsys dwmapi uxtheme msimg32 mpr cfgmgr32 wintrust d3d11 dxgi hid dsound opengl32 glu32 mf mfplat mfreadwrite mfuuid avicap32 vfw32 oleacc winusb cabinet win32u msasn1 dwrite d2d1 bcryptprimitives kernelbase wow64 d3dcompiler_47 msi wsock32 webservices'.split())
os_dlls={n+'.dll' for n in os_dlls}|{'winspool.drv'}
files=[p for p in root.rglob('*') if p.suffix.lower() in {'.exe','.dll','.pyd'}]
known={p.name.lower() for p in files};missing={};scanned=0
for path in files:
    try:
        pe=pefile.PE(str(path),fast_load=True)
        pe.parse_data_directories(directories=[1,13]);scanned+=1
        assert pe.FILE_HEADER.Machine==0x8664, str(path)
        for entry in getattr(pe,'DIRECTORY_ENTRY_IMPORT',[])+getattr(pe,'DIRECTORY_ENTRY_DELAY_IMPORT',[]):
            name=entry.dll.decode().lower()
            if name not in known and name not in os_dlls and not name.startswith(('api-ms-win-','ext-ms-win-')):
                missing.setdefault(name,[]).append(str(path.relative_to(root)))
    except pefile.PEFormatError:
        continue
assert not missing,missing
report={'artifact':'Windows x64 portable GUI executable','pe_files_checked':scanned,
        'unresolved_non_system_dlls':missing,'korean_model_sha256_verified':True,
        'windows_execution_tested':False,'linux_launcher_startup_tested':True}
(root/'BUILD-VERIFICATION.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
