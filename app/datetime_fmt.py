"""로케일에 맞춘 날짜·시간 표시 형식.

단어와 배치 순서는 :mod:`app.locales` 의 ``time.*`` 키에서 가져온다.
예를 들어 오전/오후의 위치('오전 3:05' vs '3:05 AM')도 ``time.clock_ampm``
템플릿이 결정한다."""
from __future__ import annotations

from datetime import datetime

from . import i18n


def _clock_ampm(dt: datetime) -> str:
    h = dt.hour
    ampm = i18n.t("time.pm") if h >= 12 else i18n.t("time.am")
    h12 = h if 1 <= h <= 12 else (h - 12 if h > 12 else 12)
    return i18n.t("time.clock_ampm", ampm=ampm, h=h12, mm=f"{dt.minute:02d}")


def _date_md(dt: datetime) -> str:
    return i18n.t("time.date_md", m=dt.month, d=dt.day)


def fmt_heartbeat(ms: int) -> str:
    if not ms:
        return "—"
    return i18n.t("time.heartbeat_sec", n=f"{ms / 1000:g}")


def fmt_relative(ms: int) -> str:
    if not ms:
        return ""
    dt = datetime.fromtimestamp(ms / 1000)
    now = datetime.now()
    if dt.date() == now.date():
        return i18n.t("time.today", rest=_clock_ampm(dt))
    if dt.year == now.year:
        return i18n.t("time.datetime_md", m=dt.month, d=dt.day,
                      hm=f"{dt.hour:02d}:{dt.minute:02d}")
    return dt.strftime("%Y.%m.%d %H:%M")


def fmt_card_timestamp(ms: int) -> str:
    if not ms:
        return ""
    dt = datetime.fromtimestamp(ms / 1000)
    now = datetime.now()
    if dt.date() == now.date():
        return _clock_ampm(dt)
    if dt.year == now.year:
        return _date_md(dt)
    return dt.strftime("%Y.%m.%d")
