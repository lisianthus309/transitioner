"""Conservative image-based case refinement. Never edits spelling or numeric values."""
from functools import lru_cache
import os
from pathlib import Path
import cv2
import numpy as np


@lru_cache(maxsize=1)
def vocabulary():
    path=Path(__file__).resolve().parent/'learning'/'english_words_500.txt'
    if not path.is_file():
        return frozenset()
    return frozenset(path.read_text(encoding='utf-8').splitlines())


def eligible(text):
    return (text.isascii() and text.isalpha() and text.casefold() in vocabulary() and
            (text.islower() or text.isupper() or text.istitle()))


def lowercase_initial_evidence(pixels,word):
    """Reject a proposed lowercase initial when it is visibly taller than x-height."""
    if word[0].lower() in 'bdfghjklpqty' or not any(ch in 'aceimnorsuvwxz' for ch in word[1:].lower()):
        return False
    _,ink=cv2.threshold(pixels,0,255,cv2.THRESH_BINARY_INV|cv2.THRESH_OTSU)
    count,_,stats,_=cv2.connectedComponentsWithStats(ink,8)
    components=[tuple(row) for row in stats[1:] if row[cv2.CC_STAT_AREA]>=6]
    if len(components)<2:
        return False
    median=float(np.median([row[cv2.CC_STAT_HEIGHT] for row in components]))
    components=[row for row in components if row[cv2.CC_STAT_HEIGHT]>=max(3,median*.5)]
    components.sort(key=lambda row:row[cv2.CC_STAT_LEFT])
    if len(components)<2:
        return False
    first,*rest=components
    return first[cv2.CC_STAT_HEIGHT] <= min(row[cv2.CC_STAT_HEIGHT] for row in rest)*1.15


def refine(prepared, original, psm=7, baseline_confidence=None, available=None):
    if os.environ.get('TRANSITIONER_CASE_REFINEMENT','on')=='off' or not eligible(original):
        return original
    if available is None:
        import pytesseract
        available=set(pytesseract.get_languages())
    if 'eng_case' not in available or 'eng_best' not in available:
        return original
    from native_ocr import read,NativeUnavailable
    try:
        if baseline_confidence is None:
            baseline,baseline_confidence=read(prepared,'eng_best',psm,True)
            if baseline!=original:
                return original
        if baseline_confidence>=75:
            return original
        candidate,confidence=read(prepared,'eng_case',psm,True)
        if (confidence>=94 and candidate.isascii() and candidate.isalpha() and candidate.casefold()==original.casefold() and
            (candidate.islower() or candidate.isupper() or candidate.istitle())):
            if original.istitle() and candidate.islower() and not lowercase_initial_evidence(prepared,original):
                return original
            return candidate
    except NativeUnavailable:
        pass
    return original
