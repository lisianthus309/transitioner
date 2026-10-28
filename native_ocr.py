"""Reusable thread-local Tesseract C API, with no subprocess/model reload per cell."""
import atexit
from collections import OrderedDict
import ctypes as ct
from ctypes.util import find_library
import os
from pathlib import Path
import sys
import threading
import numpy as np

class NativeUnavailable(RuntimeError):
    pass

_library = None
_dll_directories = []
_load_lock = threading.Lock()
_handles_lock = threading.Lock()
_handles = set()
_local = threading.local()


def _load():
    global _library
    with _load_lock:
        if _library is not None:
            return _library
        if os.name == 'nt':
            roots = [Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))/'tesseract',
                     Path('C:/Program Files/Tesseract-OCR')]
            candidates = [p for root in roots for p in sorted(root.glob('*tesseract*.dll'))]
            for root in roots:
                if root.is_dir():
                    _dll_directories.append(os.add_dll_directory(str(root)))
        else:
            candidates = [find_library('tesseract')]
        error = None
        for candidate in candidates:
            if not candidate:
                continue
            try:
                lib = ct.CDLL(str(candidate))
                definitions = {
                    'TessBaseAPICreate': ([],ct.c_void_p),
                    'TessBaseAPIDelete': ([ct.c_void_p],None),
                    'TessBaseAPIInit3': ([ct.c_void_p,ct.c_char_p,ct.c_char_p],ct.c_int),
                    'TessBaseAPISetPageSegMode': ([ct.c_void_p,ct.c_int],None),
                    'TessBaseAPISetVariable': ([ct.c_void_p,ct.c_char_p,ct.c_char_p],ct.c_bool),
                    'TessBaseAPISetImage': ([ct.c_void_p,ct.c_void_p,ct.c_int,ct.c_int,ct.c_int,ct.c_int],None),
                    'TessBaseAPIGetUTF8Text': ([ct.c_void_p],ct.c_void_p),
                    'TessBaseAPIGetTsvText': ([ct.c_void_p,ct.c_int],ct.c_void_p),
                    'TessDeleteText': ([ct.c_void_p],None),
                    'TessBaseAPIClear': ([ct.c_void_p],None),
                    'TessBaseAPIMeanTextConf': ([ct.c_void_p],ct.c_int),
                    'TessBaseAPIClearAdaptiveClassifier': ([ct.c_void_p],None),
                    'TessVersion': ([],ct.c_char_p),
                    'TessBaseAPIRecognize': ([ct.c_void_p,ct.c_void_p],ct.c_int),
                    'TessMonitorCreate': ([],ct.c_void_p),
                    'TessMonitorDelete': ([ct.c_void_p],None),
                    'TessMonitorSetDeadlineMSecs': ([ct.c_void_p,ct.c_int],None),
                }
                for name,(args,result) in definitions.items():
                    function = getattr(lib,name)
                    function.argtypes = args
                    function.restype = result
                _library = lib
                return lib
            except (OSError,AttributeError) as exc:
                error = exc
        raise NativeUnavailable('Tesseract C API unavailable') from error


def _release(handle):
    with _handles_lock:
        if handle in _handles:
            _handles.remove(handle)
            _library.TessBaseAPIDelete(handle)


@atexit.register
def _close():
    for handle in list(_handles):
        _release(handle)


def read(image, lang, psm=6, with_confidence=False, output="text", timeout=30):
    lib = _load()
    datapath = os.environ.get('TESSDATA_PREFIX')
    key = (datapath,lang)
    engines = getattr(_local,'engines',None)
    if engines is None:
        engines = _local.engines = OrderedDict()
    if key not in engines:
        handle = lib.TessBaseAPICreate()
        if not handle:
            raise NativeUnavailable('Could not create Tesseract engine')
        result = lib.TessBaseAPIInit3(handle,datapath.encode('utf-8') if datapath else None,lang.encode('utf-8'))
        if result:
            lib.TessBaseAPIDelete(handle)
            raise NativeUnavailable('Could not initialize requested OCR language')
        lib.TessBaseAPISetVariable(handle,b'classify_enable_learning',b'0')
        with _handles_lock:
            _handles.add(handle)
        engines[key] = handle
        if len(engines)>3:
            _,old = engines.popitem(last=False)
            _release(old)
    engines.move_to_end(key)
    handle = engines[key]
    pixels = np.ascontiguousarray(image,dtype=np.uint8)
    if pixels.ndim==2:
        channels=1
    elif pixels.ndim==3 and pixels.shape[2]==3:
        channels=3
    else:
        raise ValueError('Expected an 8-bit grayscale or RGB image')
    if output not in ('text','tsv'):
        raise ValueError('Unsupported OCR output format')
    height,width = pixels.shape[:2]
    lib.TessBaseAPIClearAdaptiveClassifier(handle)
    lib.TessBaseAPISetPageSegMode(handle,psm)
    lib.TessBaseAPISetImage(handle,pixels.ctypes.data,width,height,channels,pixels.strides[0])
    pointer = None
    monitor = lib.TessMonitorCreate()
    if not monitor:
        lib.TessBaseAPIClear(handle)
        raise NativeUnavailable('Could not create OCR deadline monitor')
    try:
        lib.TessMonitorSetDeadlineMSecs(monitor,int(timeout*1000))
        if lib.TessBaseAPIRecognize(handle,monitor):
            raise RuntimeError(f'OCR recognition failed or exceeded its {timeout}-second deadline')
        pointer = lib.TessBaseAPIGetUTF8Text(handle) if output=='text' else lib.TessBaseAPIGetTsvText(handle,0)
        if not pointer:
            raise NativeUnavailable('OCR engine did not return text')
        text = ct.string_at(pointer).decode('utf-8')
        if output=='text':
            text=text.strip()
        return (text,lib.TessBaseAPIMeanTextConf(handle)) if with_confidence else text
    finally:
        if pointer:
            lib.TessDeleteText(pointer)
        lib.TessBaseAPIClear(handle)
        lib.TessMonitorDelete(monitor)


def clear_current_thread():
    engines=getattr(_local,'engines',{})
    for handle in list(engines.values()):
        _release(handle)
    engines.clear()


def version():
    return _load().TessVersion().decode('ascii')
