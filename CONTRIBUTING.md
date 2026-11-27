# 기여 시 Git 커밋 개인정보 규칙

이 저장소의 커밋에는 이메일 주소를 넣지 않습니다. 작성자와 커미터의 이메일 필드를
비우고, 커밋 메시지와 공동 작성자 표기에도 이메일 주소를 넣지 않습니다. GitHub의
비공개 주소와 `noreply` 주소도 사용하지 않습니다.

예를 들어 이름을 지정한 뒤 두 이메일 환경 변수를 빈 값으로 설정해 커밋합니다.

```sh
GIT_AUTHOR_NAME='Cyber Knights Korean Localization' GIT_AUTHOR_EMAIL='' \
GIT_COMMITTER_NAME='Cyber Knights Korean Localization' GIT_COMMITTER_EMAIL='' \
git commit -m '변경 내용'
```

공개하기 전에 대상 브랜치와 태그에서 닿을 수 있는 모든 커밋의 작성자·커미터 필드와
메시지를 검사합니다. GitHub가 빈 이메일을 허용하지 않거나 서명이 이메일을 노출한다면
주소가 포함된 커밋을 올리지 말고 원인을 해결합니다. 과거 이력의 이메일을 제거해도
기존 클론과 캐시에 남은 커밋은 자동으로 사라지지 않을 수 있습니다.
