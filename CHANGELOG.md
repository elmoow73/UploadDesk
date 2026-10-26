# 변경 이력

## 1.1.1 — 2026-10-26

- 변경 내용: Responsive-browser-window-with-1980x1080-default
- 호환성: Backward-compatible

## 1.1.1 변경 사항

- 업로드 브라우저의 기본 창 크기를 1980×1080으로 설정하고, 창 크기 변경 시 페이지 표시 영역도 함께 조정하도록 수정. UploadDesk와 UploadDeskIR52에 공통 적용.
- 호환성: 기존 로그인·등록 기능 유지.

## 1.1.0 — 2026-10-26

- 변경 내용: UploadDesk-and-UploadDeskIR52-English-launchers-and-IR52-article-upload
- 호환성: Backward-compatible

## 1.1.0 변경 사항

- 프로그램명을 UploadDesk, IR52 프로그램명을 UploadDeskIR52로 변경.
- 실행·설치·GitHub 배포 파일명을 Run.cmd, Setup.cmd, PublishGitHub.cmd로 변경하고 문서와 배포 ZIP 이름을 갱신. 기존 업로드 기능은 유지하며 실행 파일 바로가기는 새 이름으로 변경 필요.
- 내용 자동 입력을 프로그램 시작 시 기본 체크로 변경.
- 안내 문구를 ‘등록 페이지 도착 후 내용 자동 입력 (선택 해제 시 본문 입력하지 않음)’으로 변경.
- 체크 해제로 기존 수동 진행 가능.
- UploadDeskIR52의 매일경제 기사 불러오기, DB 선택 및 기사 등록 폼 자동 입력 기능 추가. 실제 로그인·등록 화면 검증은 아직 미수행.
- 호환성: 기존 업로드 기능과 수동 입력 선택을 유지. 이름이 바뀐 실행 파일의 기존 바로가기는 수정 필요.

## 1.0.0 — 2026-10-22

- 변경 내용: Initial-stable-release
- 호환성: Initial stable release

## 최초 정식 버전 기능 구성

- 그룹웨어 로그인 및 KOITA 관리자 등록 화면 이동
- HWPX 온라인 보도일 추출, 첫 페이지 JPG 생성 및 가로 700px 변환
- 등록 폼 기본 항목, 본문 이미지·문구, 원본 첨부 대기 목록 입력
- News DB 기사 선택 및 관련사이트 마지막 입력
- 입력값 확인, 단계별 오류 표시, 비밀번호 저장·기록 금지
- 최종 게시물 저장 버튼은 자동으로 누르지 않음

사용자의 최종 승인 후 정식 버전과 Git 태그를 확정했습니다.
