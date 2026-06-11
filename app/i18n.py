"""국제화(i18n) 지원.

언어는 앱 시작 시 한 번 결정되며, 실행 중 바꾸려면 다시 시작해야 한다.
이미 만들어진 위젯의 텍스트는 갱신하지 않기 때문이다.

새 언어 추가: ``app/locales/<code>.py`` 에 ``STRINGS`` 를 정의해
``app/locales/__init__.py`` 의 ``TABLES`` 에 등록한 뒤, 아래
:data:`SUPPORTED_LANGUAGES` 와 :data:`LANGUAGE_NAMES` 에 추가한다."""
from __future__ import annotations

from PySide6.QtCore import QLocale

from .locales import TABLES

# 지원 언어(ISO 639-1 코드). 첫 번째가 기준 언어이자 폴백 대상이다.
SUPPORTED_LANGUAGES = ("ko", "en", "ja")
DEFAULT_LANGUAGE = SUPPORTED_LANGUAGES[0]

LANGUAGE_NAMES = {
    "ko": "한국어",
    "en": "English",
    "ja": "日本語",
}

_current = DEFAULT_LANGUAGE


def detect_os_language() -> str:
    code = QLocale.system().name().split("_", 1)[0].lower()
    return code if code in SUPPORTED_LANGUAGES else "en"


def resolve_language(saved: str | None) -> str:
    if saved and saved in SUPPORTED_LANGUAGES:
        return saved
    return detect_os_language()


def set_language(code: str) -> None:
    global _current
    _current = code if code in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def current_language() -> str:
    return _current


def t(key: str, /, **kwargs) -> str:
    """키가 현재 언어 사전에 없으면 기준 언어로, 그래도 없으면 키 문자열 자체로 폴백."""
    table = TABLES.get(_current) or TABLES[DEFAULT_LANGUAGE]
    text = table.get(key)
    if text is None:
        text = TABLES[DEFAULT_LANGUAGE].get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return text
    return text
