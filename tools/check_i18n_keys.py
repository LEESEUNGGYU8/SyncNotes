"""i18n 키 정합성 검사.

코드에서 t("...") 로 참조한 모든 키가 app/locales/ko.py(기준 언어)에
존재하는지, 그리고 en/ja 사전이 ko 와 같은 키 집합을 갖는지 확인한다.
누락 시 0이 아닌 종료 코드를 반환한다(CI/사전 점검용)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DIRS = [ROOT / "app", ROOT / "main.py"]

# i18n.t("key") 호출의 첫 인자(문자열 리터럴) 추출.
# 번역은 항상 i18n.t(...) 형태로 호출하므로 그 패턴만 매칭한다.
_CALL = re.compile(r"""i18n\.t\(\s*(['"])(?P<key>[^'"]+)\1""")


def used_keys() -> set[str]:
    keys: set[str] = set()
    files: list[Path] = []
    for p in SRC_DIRS:
        if p.is_file():
            files.append(p)
        else:
            files += [f for f in p.rglob("*.py")
                      if "__pycache__" not in f.parts and "locales" not in f.parts]
    for f in files:
        for m in _CALL.finditer(f.read_text(encoding="utf-8")):
            keys.add(m.group("key"))
    return keys


def dict_keys(lang: str) -> set[str]:
    from importlib import import_module
    mod = import_module(f"app.locales.{lang}")
    return set(mod.STRINGS.keys())


def main() -> int:
    sys.path.insert(0, str(ROOT))
    used = used_keys()
    ko = dict_keys("ko")
    en = dict_keys("en")
    ja = dict_keys("ja")

    problems = 0
    missing_in_ko = sorted(used - ko)
    if missing_in_ko:
        problems += len(missing_in_ko)
        print(f"[코드에서 쓰였으나 ko 사전에 없음] {len(missing_in_ko)}개")
        for k in missing_in_ko:
            print("  -", k)

    for lang, ks in (("en", en), ("ja", ja)):
        miss = sorted(ko - ks)
        extra = sorted(ks - ko)
        if miss:
            problems += len(miss)
            print(f"[{lang} 사전에 누락(ko 기준)] {len(miss)}개")
            for k in miss:
                print("  -", k)
        if extra:
            print(f"[{lang} 사전에 ko 에 없는 잉여 키] {len(extra)}개")
            for k in extra:
                print("  -", k)

    unused = sorted(ko - used)
    if unused:
        print(f"[ko 사전에 있으나 코드에서 안 쓰임] {len(unused)}개 (경고)")

    print(f"\n요약: 코드 사용 키 {len(used)} / ko {len(ko)} / en {len(en)} / ja {len(ja)}")
    if problems:
        print(f"문제 {problems}건")
        return 1
    print("정합성 OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
