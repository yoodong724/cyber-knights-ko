# Cyber Knights: Flashpoint 한글패치

**[26198171 한글패치 다운로드](https://github.com/yoodong724/cyber-knights-ko/releases/tag/26198171)** · [변경 내역](CHANGELOG.md)

## 대응 버전

| 항목 | 버전 |
|---|---|
| 한글패치 | **26198171** |
| 게임 | Steam Windows판, App ID 1021210, 빌드 **26198171** (게임 버전 2.7.105) |
| 설치본 확인일 | **2026년 10월 26일** (한국 시간) |

게임 빌드와 업데이트 날짜: [SteamDB](https://steamdb.info/app/1021210/patchnotes/).

게임이 업데이트되어 빌드가 다르면 설치기가 설치를 거부합니다. 대응 빌드의 패치가 나올 때까지 기다려 주십시오.

타이틀·저장 불러오기·초반 튜토리얼의 한글 표시를 확인했습니다. 전체 플레이 테스트는 아닙니다.
이미지는 튜토리얼·메뉴 배너 일부만 한글화했으며 영문 이미지가 남아 있습니다.

## 설치 방법

1. 게임과 Steam을 종료합니다.
2. 기존 패치가 설치돼 있다면 기존 `cyberknights-ko/uninstall.cmd`로 원본을 복구하고, 기존 `cyberknights-ko` 폴더를 다른 이름이나 위치에 보관합니다. 게임 폴더의 `.cyberknights-ko-backup` 폴더는 지우지 않습니다.
3. 다운로드 페이지의 **Assets**에서 `cyberknights-ko-26198171.zip`(본문 + 일부 이미지)을 받습니다.
4. Steam 라이브러리에서 게임을 우클릭하고 **관리 → 로컬 파일 탐색**으로 게임 폴더를 엽니다.
5. ZIP 안의 `cyberknights-ko` 폴더를 `CyberKnights.exe`가 있는 폴더에 넣습니다.
6. `cyberknights-ko/install.cmd`를 실행하고, 표시된 게임 폴더가 맞으면 `y`를 입력합니다.
7. 게임을 실행하고 게임 언어에서 **한국어**를 선택합니다.

게임은 로컬 NTFS 드라이브에 있어야 하며 Windows PowerShell 5.1을 사용합니다. 별도 프로그램 설치는 필요 없습니다.

## 패치 업데이트·제거

게임을 종료한 뒤 `cyberknights-ko/uninstall.cmd`를 실행하면 원본으로 복구됩니다.
`cyberknights-ko/verify.cmd`는 설치 상태만 검사하며 게임 파일을 바꾸지 않습니다.
새 패치를 설치할 때는 먼저 기존 패치를 제거한 뒤 위 순서로 설치합니다. 새 ZIP을 기존 폴더에 덮어 풀지 마십시오.

이미 시작한 캠페인의 저장된 인물 이름은 바뀌지 않습니다.

## 저장소 소스 안내

게임 대사와 줄거리의 불필요한 노출을 줄이기 위해 번역 본문·수정 이미지·빌드 입력은
저장소에서 제외하고 제작 도구와 설치기 소스만 보관합니다.
**이 저장소의 소스와 원본 게임만으로는 한글패치를 재현할 수 없습니다.**
패치를 사용할 때는 Releases에 첨부한 설치용 ZIP을 받으십시오. GitHub의 `Source code` ZIP은 제작 도구·설치기 소스입니다.

- `tools/`, `gloc/`: 원본 locale 추출, 한국어 locale 생성, 배포 ZIP 생성 도구 (Python 3.11+ 표준 라이브러리)
- `templates/ckf-distribution/`: Windows 설치기 소스 (`install.cmd`, `uninstall.cmd`, `verify.cmd`, `Patch.cs`)
- 빌드 절차와 필요한 비공개 입력: [docs/BUILD.md](docs/BUILD.md)
- 권리와 라이선스: [NOTICE.md](NOTICE.md)
