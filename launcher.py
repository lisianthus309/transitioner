"""Desktop entry point for the Windows distribution."""
import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path
from multiprocessing import freeze_support


def configure_utf8():
    """Use UTF-8 for child Python processes and Windows console text."""
    os.environ['PYTHONUTF8'] = '1'
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    if os.name == 'nt':
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='backslashreplace')


def main():
    configure_utf8()
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    engine = root / 'tesseract'
    portable = root / 'runtime' / 'Library' / 'bin'
    if portable.exists():
        engine = portable
        os.environ['TESSDATA_PREFIX'] = str(root / 'runtime' / 'share' / 'tessdata')
    elif engine.exists():
        os.environ['PATH'] = str(engine) + os.pathsep + os.environ.get('PATH', '')
        os.environ['TESSDATA_PREFIX'] = str(engine / 'tessdata')
    if engine.exists():
        os.environ['PATH'] = str(engine) + os.pathsep + os.environ.get('PATH', '')
    os.environ.setdefault('OMP_THREAD_LIMIT', '1')
    if '--self-test' in sys.argv:
        from io import BytesIO
        from PIL import Image, ImageDraw, ImageFont
        from openpyxl import load_workbook
        from ocr import recognize, workbook
        image = Image.new('RGB',(500,180),'white')
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',28)
        for x in (10,250,490): draw.line((x,10,x,170),fill='black',width=2)
        for y in (10,90,170): draw.line((10,y,490,y),fill='black',width=2)
        for xy,text in [((30,30),'한국어'),((270,30),'123'),((30,110),'서울'),((270,110),'031')]:
            draw.text(xy,text,font=font,fill='black')
        table,_ = recognize(image,'kor+eng')
        assert table.shape == (2,2)
        assert ''.join(table.iat[0,0].split()) == '한국어'
        assert table.iat[1,1] == '031'
        assert load_workbook(BytesIO(workbook([table]))).active['B2'].value == '031'
        assert (root/'app.py').exists()
        from text_checks import run_text_checks
        run_text_checks()
        print('PASS: bundled Korean OCR and Excel export')
        return
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    url = f'http://127.0.0.1:{port}'
    def open_when_ready():
        for _ in range(120):
            try:
                with urllib.request.urlopen(url+'/_stcore/health', timeout=1) as response:
                    if response.read() == b'ok':
                        ready = os.environ.get('TRANSITIONER_READY_FILE')
                        if ready:
                            target = Path(ready)
                            pending = target.with_suffix('.tmp')
                            pending.write_text(url, encoding='utf-8')
                            pending.replace(target)
                        if os.environ.get('TRANSITIONER_MANAGED') != '1':
                            webbrowser.open(url)
                        return
            except OSError:
                pass
            time.sleep(.5)
        print('브라우저가 열리지 않았습니다. 콘솔 오류를 확인하세요.')
    threading.Thread(target=open_when_ready, daemon=True).start()
    from streamlit.web import bootstrap
    flags = {
        'server.address': '127.0.0.1', 'server.port': port,
        'server.headless': True, 'server.fileWatcherType': 'none',
        'browser.gatherUsageStats': False, 'global.developmentMode': False,
    }
    bootstrap.load_config_options(flags)
    bootstrap.run(str(root/'app.py'), False, [], flags)

if __name__ == '__main__':
    freeze_support()
    main()
