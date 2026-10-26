"""Preview by default. Version, commit, tag and push only with --approve."""
import argparse
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile
import hashlib
import os
import tempfile

ROOT = Path(__file__).resolve().parent
VERSION = ROOT / 'VERSION.json'
CONFIG = ROOT / 'release_config.json'
LEGACY_LAUNCHERS = ['실행.cmd', '설치.cmd', 'GitHub 업로드.cmd', 'UploadingIR52.cmd', 'UploadingIR52-README.md']


def next_version(current, bump):
    if current is None:
        if bump != 'initial':
            raise ValueError('최초 배포는 initial을 선택해야 합니다.')
        return '1.0.0'
    if not re.fullmatch(r'\d+\.\d+\.\d+', current):
        raise ValueError('현재 버전 형식이 올바르지 않습니다.')
    major, minor, patch = map(int, current.split('.'))
    if bump == 'major':
        return f'{major + 1}.0.0'
    if bump == 'minor':
        return f'{major}.{minor + 1}.0'
    if bump == 'patch':
        return f'{major}.{minor}.{patch + 1}'
    raise ValueError('정식 배포 이후에는 major/minor/patch를 선택하세요.')


def git(*args, capture=False, check=True):
    return subprocess.run(['git', *args], cwd=ROOT, check=check,
                          text=True, encoding='utf-8', capture_output=capture)


def release_files():
    # Explicit source allowlist: never stage the whole working directory.
    fixed = ['VERSION.json', 'release_config.json', 'CHANGELOG.md', 'AGENTS.md',
             '.gitignore', 'README.md', 'release.py', 'Run.cmd', 'Setup.cmd', 'PublishGitHub.cmd',
             'RegistrationPageCode.txt', 'UploadDeskIR52.cmd', 'UploadDeskIR52-README.md']
    source = ROOT / 'koita_stage1'
    files = fixed + [p.relative_to(ROOT).as_posix() for p in source.glob('*.py')]
    files += ['koita_stage1/requirements.txt', 'koita_stage1/README.md', 'koita_stage1/.gitignore',
              'koita_stage1/login_selectors.json']
    return sorted(path for path in files if (ROOT / path).is_file())


def write_metadata(state, target, bump, summary):
    state['version'] = target
    VERSION.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    compatibility = 'Breaking' if bump == 'major' else 'Backward-compatible' if bump != 'initial' else 'Initial stable release'
    day = datetime.now(timezone(timedelta(hours=9))).date().isoformat()
    changelog = ROOT / 'CHANGELOG.md'
    text = changelog.read_text(encoding='utf-8')
    if bump == 'initial':
        text = text.replace('## 승인 대기 — 최초 정식 버전 1.0.0 예정', '## 최초 정식 버전 기능 구성')
        text = text.replace('정식 버전과 Git 태그는 사용자의 최종 승인 후 확정합니다.', '사용자의 최종 승인 후 정식 버전과 Git 태그를 확정했습니다.')
    entry = f'\n## {target} — {day}\n\n- 변경 내용: {summary.strip()}\n- 호환성: {compatibility}\n'
    changelog.write_text(text.replace('# 변경 이력\n', '# 변경 이력\n' + entry, 1), encoding='utf-8')


def package_release(version, directory=None):
    directory = Path(directory) if directory else ROOT.parent
    destination = directory / f'UploadDesk-v{version}.zip'
    if destination.exists():
        raise ValueError('같은 버전의 ZIP이 이미 있습니다. 기존 배포 파일을 덮어쓰지 않습니다.')
    files = release_files()
    prefix = f'UploadDesk-v{version}/'
    descriptor, temporary = tempfile.mkstemp(prefix='UploadDesk-', suffix='.zip.tmp', dir=directory)
    os.close(descriptor)
    try:
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for filename in files:
                archive.write(ROOT / filename, prefix + filename)
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip() is not None:
                raise ValueError('ZIP 무결성 검사 실패')
            if json.loads(archive.read(prefix + 'VERSION.json'))['version'] != version:
                raise ValueError('ZIP 내부 버전 불일치')
            for filename in files:
                if archive.read(prefix + filename) != (ROOT / filename).read_bytes():
                    raise ValueError('ZIP 내용과 현재 소스 불일치')
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    print('ZIP:', destination)
    print('SHA256:', hashlib.sha256(destination.read_bytes()).hexdigest())
    return destination


def publish(args):
    state = json.loads(VERSION.read_text(encoding='utf-8'))
    config = json.loads(CONFIG.read_text(encoding='utf-8'))
    remote = config['repository']
    branch = config['branch']
    if not re.fullmatch(r'https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?', remote):
        raise ValueError('GitHub HTTPS 저장소 주소만 허용합니다. 인증정보를 주소에 넣지 마세요.')
    if not re.fullmatch(r'[A-Za-z0-9_-]+', branch):
        raise ValueError('지원하지 않는 배포 브랜치 이름입니다.')
    publish_current = getattr(args, 'publish_current', False)
    local_only = getattr(args, 'local_only', False)
    target = state['version'] if args.push_only or publish_current else next_version(state['version'], args.bump)
    if target is None:
        raise ValueError('아직 확정된 버전이 없습니다.')
    print(f'Version: {state["version"] or "approval pending"} -> {target}')
    print(f'Repository: {remote}\nBranch: {branch}\nTag: v{target}')
    if not args.approve:
        print('PREVIEW ONLY: no version change, commit, tag or push. Final approval is required.')
        return
    if not args.push_only and not publish_current and not args.summary.strip():
        raise ValueError('변경 내용 --summary가 필요합니다.')
    # Verify before touching release metadata.
    subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'koita_stage1', '-v'], cwd=ROOT, check=True)
    if local_only:
        if args.push_only or publish_current:
            raise ValueError('local-only는 새 버전 확정에만 사용합니다.')
        if (ROOT.parent / f'UploadDesk-v{target}.zip').exists():
            raise ValueError('같은 버전의 ZIP이 이미 있습니다.')
        write_metadata(state, target, args.bump, args.summary)
        package_release(target)
        print('Local release complete. GitHub upload is still pending.')
        return
    if not (ROOT / '.git').exists():
        if args.push_only:
            raise ValueError('Git 저장소가 없습니다.')
        git('init', '-b', branch)
    existing = git('remote', 'get-url', 'origin', capture=True, check=False)
    if existing.returncode == 0 and existing.stdout.strip().removesuffix('.git') != remote.removesuffix('.git'):
        raise ValueError('기존 origin이 설정 주소와 다릅니다. 자동 변경하지 않았습니다.')
    # Read-only remote preflight also exercises GitHub authentication.
    git('ls-remote', remote, capture=True)
    if existing.returncode != 0:
        git('remote', 'add', 'origin', remote)
    if not args.push_only:
        for key in ('user.name', 'user.email'):
            if git('config', '--get', key, capture=True, check=False).returncode:
                raise ValueError('Git 작성자 이름/이메일 설정이 필요합니다. 전역 설정은 자동 변경하지 않습니다.')
        allowed = release_files()
        staged = git('-c', 'core.quotepath=false', 'diff', '--cached', '--name-only', capture=True).stdout.splitlines()
        if set(staged) - set(allowed) - set(LEGACY_LAUNCHERS):
            raise ValueError('배포 허용 목록 밖의 파일이 스테이징되어 있습니다. 검토 후 다시 실행하세요.')
        if git('rev-parse', '--verify', f'refs/tags/v{target}', capture=True, check=False).returncode == 0:
            raise ValueError('같은 버전 태그가 이미 있습니다. 업로드 재시도에는 --push-only를 사용하세요.')
        if not publish_current:
            write_metadata(state, target, args.bump, args.summary)
            package_release(target)
        obsolete = [path for path in LEGACY_LAUNCHERS
                    if not (ROOT / path).exists()
                    and git('ls-files', '--', path, capture=True).stdout.strip()]
        git('add', '--all', '--', *allowed, *obsolete)
        git('commit', '-m', f'Release v{target}: {args.summary.strip()}')
        git('tag', '-a', f'v{target}', '-m', f'UploadDesk {target}')
    else:
        if git('rev-parse', f'v{target}^{{commit}}', capture=True).stdout != git('rev-parse', 'HEAD', capture=True).stdout:
            raise ValueError('현재 HEAD와 버전 태그가 다릅니다. 업로드 대상을 검토하세요.')
    # Both updates succeed together or neither is pushed; never force-push.
    git('push', '--atomic', 'origin', f'HEAD:refs/heads/{branch}', f'refs/tags/v{target}')
    print(f'Published UploadDesk v{target}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bump', choices=['initial', 'major', 'minor', 'patch'], default='initial')
    parser.add_argument('--summary', default='')
    parser.add_argument('--approve', action='store_true', help='Explicit final release approval')
    parser.add_argument('--push-only', action='store_true', help='Retry pushing an already committed/tagged release')
    parser.add_argument('--local-only', action='store_true', help='Finalize version and create ZIP, without GitHub access')
    parser.add_argument('--publish-current', action='store_true', help='Commit/tag/push an approved local version without incrementing it')
    args = parser.parse_args()
    try:
        publish(args)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print('Release stopped:', str(error), file=sys.stderr)
        print('If commit/tag succeeded but push failed, resolve GitHub access then retry with --push-only --approve.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
