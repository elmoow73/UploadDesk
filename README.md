# UploadingMan

KOITA 보도자료 등록 화면의 입력을 준비하는 Windows 프로그램입니다. 현재 버전은 `VERSION.json`과 프로그램 제목 표시줄에서 확인할 수 있습니다.

## 실행

`실행.cmd`를 더블 클릭합니다. 상세 사용법은 `koita_stage1/README.md`를 참고하세요. 한글 데스크톱 프로그램, Chrome 또는 Edge, Python이 필요합니다. 다른 PC에서는 `koita_stage1/requirements.txt`로 패키지를 설치해야 합니다. 로그인 비밀번호는 저장/로그 기록하지 않으며 최종 게시물 저장은 자동으로 누르지 않습니다.

ZIP은 소스와 설치·실행 파일을 담은 배포본입니다. 다른 폴더나 PC에 압축을 풀면 `설치.cmd`를 먼저 실행한 후 `실행.cmd`를 사용하세요. 가상환경은 경로가 바뀌면 재사용하기 어려워 ZIP에 넣지 않습니다. 원본 HWPX, News DB, 생성 이미지와 비밀번호도 포함하지 않습니다.

승인된 모든 버전은 프로젝트 상위 폴더에 `UploadingMan-vX.Y.Z.zip`으로 생성하고 무결성·내부 버전·소스 일치를 검사합니다. 먼저 로컬 버전 확정과 ZIP만 만들려면 `release.py --local-only --bump initial --summary "최초 정식 배포" --approve`를 사용합니다. 이후 이미 확정한 버전을 GitHub에 올릴 때는 `release.py --publish-current --approve`를 사용합니다. 다음 버전부터는 major/minor/patch에 맞춰 같은 ZIP 작업을 반복합니다.

## 버전 정책

| 종류 | 변경 내용 | 호환성 | 예시 |
|---|---|---|---|
| 메이저 X.0.0 | 공개 API 또는 사용 방식의 비호환 변경 | Breaking | 함수 이름 변경, 필수 파라미터 삭제 |
| 마이너 x.Y.0 | 기존 기능과 호환되는 기능 추가 | 유지 | 새 기능/함수, 선택 파라미터 추가 |
| 패치 x.y.Z | 호환되는 버그·보안 수정 | 유지 | 날짜 계산 오류, 보안 패치 |

예: 1.0.0 → 버그 수정 1.0.1 → 새 기능 1.1.0 → 비호환 변경 2.0.0. 새 버전을 확정할 때 하위 자리수는 0으로 초기화합니다. 변경 내용과 호환성은 CHANGELOG.md에 남깁니다.

## GitHub 업로드

대상 후보는 `https://github.com/elmoow73/UploadingMan`입니다. 계정 주소만 제공된 상태이므로 저장소 생성 여부와 공개/비공개 여부는 아직 미확정입니다. `release_config.json`에서 주소를 바꿀 수 있습니다. GitHub에 빈 저장소를 준비하고 Git 인증과 Git 작성자 이름/이메일을 설정해야 업로드할 수 있습니다. GitHub 토큰/비밀번호를 코드나 설정 파일에 적지 마세요.

기본 실행은 **미리보기만** 하며 파일 변경/커밋/태그/업로드를 하지 않습니다.

```bat
koita_stage1\.venv\Scripts\python.exe release.py
```

최종 승인한 경우에만 다음 명령을 실행합니다. 테스트 → 버전 확정 → 변경 이력 → 커밋 → 버전 태그 → GitHub 업로드를 진행합니다. 실행 전에 변경 파일을 검토하세요.

```bat
koita_stage1\.venv\Scripts\python.exe release.py --bump initial --summary "최초 정식 버전" --approve
```

이후에는 변경 종류에 따라 `--bump patch`, `--bump minor`, `--bump major`를 사용합니다. 마지막 `--approve`가 없으면 계속 미리보기만 합니다. 로컬 커밋·태그까지 성공한 뒤 원격 업로드가 실패하면 접속 문제를 해결하고 아래 명령으로 같은 버전을 다시 올립니다.

```bat
koita_stage1\.venv\Scripts\python.exe release.py --push-only --approve
```

업로드는 소스 허용 목록만 스테이징하며 가상환경, 생성 이미지, HWPX 원본, News DB, 로그, 인증정보 파일은 제외합니다. 자동 업로드는 승인된 소스 커밋과 태그를 올리는 방식이며 실행 중 입력한 자료나 비밀번호는 대상이 아닙니다. Windows 설치용 EXE 제작 및 GitHub Releases 배포 파일 생성은 포함하지 않습니다.
