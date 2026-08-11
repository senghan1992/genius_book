#!/usr/bin/env python3
"""
Genius Intelligence - CI/CD Installer
===================================
GitHub Actions, GitLab CI 등에서 사용하기 위한 설치 스크립트

사용법:
    # GitHub Actions
    - name: Install Genius Intelligence
      run: |
        curl -fsSL https://raw.githubusercontent.com/genius-intelligence/genius-intelligence/main/install.sh | bash

    # GitLab CI
    - script:
        - curl -fsSL https://.../install.sh | bash

    # 직접 실행
    python3 install_ci.py
"""

import subprocess
import sys
import os


def run(cmd, check=True):
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    if check and result.returncode != 0:
        print(f"Command failed: {cmd}")
        sys.exit(1)
    return result


def main():
    print("=" * 50)
    print("Genius Intelligence CI Installer")
    print("=" * 50)

    # 1. Python 확인
    run("python3 --version")

    # 2. pip 업그레이드
    run("python3 -m pip install --upgrade pip", check=False)

    # 3. 설치
    run("python3 -m pip install genius-intelligence", check=False)

    # 4. 확인
    result = run("python3 -c 'import genius_intelligence; print("Version:", genius_intelligence.__version__)'", check=False)

    if result.returncode == 0:
        print("=" * 50)
        print("Installation successful!")
        print("=" * 50)
    else:
        print("Installation may have issues, but continuing...")

    # 5. 환경 변수 설정 (CI에서 유용)
    print("
To enable in CI, add to your workflow:")
    print("""
    env:
      GENIUS_INTELLIGENCE_ENABLED: "1"
      GENIUS_PROJECT_ROOT: ${{ github.workspace }}
""")


if __name__ == "__main__":
    main()
