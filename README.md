<p align="center">
  <img src="images/logo.png" width="1000" alt="SyncNotes">
</p>

<h1 align="center">SyncNotes</h1>

<p align="center">
  <b>같은 네트워크 안에서 메모를 실시간으로 공유·공동 편집하는 데스크톱 포스트잇 앱</b>
</p>

<p align="center">
  <a href="https://github.com/LEESEUNGGYU8/SyncNotes-releases/releases/latest">
    <img alt="Latest release" src="https://img.shields.io/github/v/release/LEESEUNGGYU8/SyncNotes-releases?label=latest&color=2563EB">
  </a>
  <img alt="Total downloads" src="https://img.shields.io/github/downloads/LEESEUNGGYU8/SyncNotes-releases/total?label=downloads&color=22C55E">
  <img alt="Platform" src="https://img.shields.io/badge/platform-Windows-3776AB">
  <img alt="License" src="https://img.shields.io/badge/license-Freeware-F59E0B">
</p>

---

## 미리보기

<p align="center">
  <img src="images/SyncNotes_main.png" width="360" alt="메인 창">
</p>

<p align="center">
  <img src="images/SyncNotes_notes.png" width="360" alt="포스트잇">
  <img src="images/SyncNotes_gif.gif" width="360" alt="SyncNotes 사용 예시">
</p>

## 주요 기능

- **실시간 공동 편집** — 같은 내부망에서 호스트/게스트로 접속해 같은 메모를 동시에 편집
- **다양한 서식** — 굵게/기울임/밑줄/취소선/하이라이트, 폰트 크기 Ctrl+휠, 글머리 기호·체크박스
- **이미지 첨부** — 첨부·붙여넣기·드래그 앤 드롭, 애니메이션 자동 재생
- **폴더 관리** — 메모를 폴더로 분류, 일괄 표시·숨기기·이동·삭제
- **나만 보기** — 메모·폴더 단위로 본인에게만 보이도록 설정 (호스트/게스트 무관)
- **수정 이력/복구** — 편집 세션 자동 기록, diff 보기, 이전 시점으로 되돌리기
- **검색 기능** — 메모 본문 전체 검색, 폴더별 보기

## 다운로드

**[최신 버전 다운로드 (클릭 시 이동)](https://github.com/LEESEUNGGYU8/SyncNotes-releases/releases/latest)**

Assets 목록에서 `SyncNotes-Setup-[버전].exe` 를 다운로드 후 설치하시면 됩니다.

> 처음 실행 시 Windows SmartScreen이 "추가 정보 > 실행"을 요구할 수 있습니다. 코드 서명을 적용하지 않은 프리웨어라 첫 실행에서만 경고가 한 번 표시됩니다.

## 자동 업데이트

프로그램을 실행 시 백그라운드에서 새 버전을 확인하고, 업데이트 필요 시 있으면 안내 창이 표시됩니다.
**지금 업데이트**를 선택하면 설치 파일을 받아 자동 설치하며, 다운로드된 설치 파일에 대한 SHA-256 해시 검증이 진행되어 무결성을 확보합니다.

## 무결성 검증

각 버전의 `version.json` 파일에 인스톨러의 SHA-256 해시가 포함되어 있습니다. 직접 확인하시려면 PowerShell에서 아래 커맨드를 입력하세요:

```powershell
Get-FileHash -Algorithm SHA256 .\SyncNotes-Setup-[버전].exe
```

커맨드 창에 표시된 해시가 `version.json` 의 `sha256` 값과 일치하는지 확인하세요.

## 빠른 시작

### 호스트 — 메모를 공유할 PC
1. SyncNotes 실행 → **호스트로 시작**
2. 닉네임 입력, 포트 확인 (기본 5555)
3. Windows 방화벽에서 해당 포트 허용

### 게스트 — 호스트에 접속할 PC
1. SyncNotes 실행 → **게스트로 접속**
2. 호스트의 IP 주소·포트·자신의 닉네임 입력

> 같은 네트워크에 있어야 하며, 호스트 PC의 IP 주소는 SyncNotes의 **참가자** 창에서 확인할 수 있습니다.

## 변경 내역

각 버전의 자세한 변경 사항은 **[Releases 페이지](https://github.com/LEESEUNGGYU8/SyncNotes-releases/releases)** 에서 확인할 수 있습니다.

## 문의 / 버그 신고

버그나 개선 요청은 [Issues 탭](https://github.com/LEESEUNGGYU8/SyncNotes-releases/issues)에 남겨주시면 감사하겠습니다.

## 라이선스

본 저장소의 배포 파일은 자유롭게 사용 가능한 **프리웨어**입니다.
인스톨러에 포함된 라이선스 폴더에서 본 소프트웨어와 함께 배포되는 오픈소스 라이브러리(Qt, PySide6, Pretendard 폰트 등)의 라이선스를 확인하실 수 있습니다.
