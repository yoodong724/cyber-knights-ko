# 패치 빌드 절차

이 저장소에는 배포 ZIP을 만드는 최소한의 코드만 있습니다. Python 3.11 이상의 표준 라이브러리만 사용합니다.
아래의 비공개 입력은 번역 본문·수정 이미지·게임에서 만든 빌드 입력이므로 저장소에 포함하지 않습니다.

| 비공개 입력 | 내용 |
|---|---|
| 원본 게임 파일 | 대상 6개(locale, 폰트, 자막, 이미지 번들 2개)와 보호 파일 2개. 패치 전 원본이어야 합니다. |
| `metadata.json` | 원문 문맥 메타데이터 |
| 번역 JSONL | 원문 snapshot의 ID와 해시에 연결된 한국어 본문 |
| 폰트 번들 | 한글 글꼴을 넣고 해시를 고정한 폰트 번들 |
| 자막 stage | 한국어 자막 번들과 fallback 폰트 번들 |
| 이미지 stage | 수정 이미지 번들 2개와 검증 기록 |

```sh
# 1. 원본 locale에서 원문 snapshot 생성
python tools/build_ckf_locale_stage.py extract --game <원본> --out <snapshot> --metadata <metadata.json>

# 2. 한국어 locale stage 생성
python tools/build_ckf_locale_stage.py stage --snapshot <snapshot> --translations <번역.jsonl> \
  --game <원본> --font <폰트-번들> --out <locale-stage>

# 3. 배포 ZIP 생성 (이미지 포함, 새 빌드의 첫 패키지는 revision 0)
python tools/build_ckf_distribution.py --authorize-package --original <원본> \
  --stage <locale-stage> --stage <자막-stage> --stage <이미지-stage> --allow-partial-images \
  --build 26198171 --game-version 2.7.105 --revision 0 --out <출력> --work <새-작업-폴더>
```

빌드 도구는 지원하는 Steam 빌드(현재 26198171, 이전 26151125·26138768·26097464·25964281·25951469·25889011 등)마다 고정한 대상 경로·보호 파일 해시와 원본 해시, stage 해시, 차분 복원 결과와 ZIP 구성 파일을 검사합니다. 다른 빌드의 원본이면 거부합니다.
같은 입력으로 다시 빌드하면 ZIP 안의 파일 내용은 배포본과 같습니다. ZIP에 기록되는 파일 시각만 달라 ZIP 전체 해시는 달라집니다.
