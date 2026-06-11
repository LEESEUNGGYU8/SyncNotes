"""언어별 문자열 사전 모음.

각 언어는 ``<code>.py`` 파일에 ``STRINGS`` 사전으로 정의한다.
새 언어를 추가하려면 파일을 만들어 아래 ``TABLES`` 에 등록하고,
``app/i18n.py`` 의 ``SUPPORTED_LANGUAGES`` 와 ``LANGUAGE_NAMES`` 에도 코드를 추가한다.

모든 사전은 한국어(``ko``)와 같은 키 집합을 공유한다. 한국어가 기준 언어이며,
다른 언어에서 키가 빠지면 :func:`app.i18n.t` 가 한국어로 폴백한다."""

from __future__ import annotations

from . import en, ja, ko

TABLES = {
    "ko": ko.STRINGS,
    "en": en.STRINGS,
    "ja": ja.STRINGS,
}
