# Genius Intelligence

코딩 어시스턴트 CLI 도구(claude code, omp, opencode, codex 등)에 **자동 통합**되는 프로젝트 단위 지식화 라이브러리.

> "반복되는 문제는 처음에만 문제일 뿐"

## 🚀 1분 설치

```bash
# Linux / macOS — omp.sh 스타일 한 줄 설치 (질문 없음, 자동으로 시스템 PATH에 설치)
curl -fsSL https://senghan1992.github.io/genius_book/install | sh

# Windows
irm https://raw.githubusercontent.com/senghan1992/genius_intelligence/main/install.ps1 | iex
```

설치 끝나면 새 셸을 열고 바로 `genius` 명령이 동작합니다.
`claude`, `omp`, `opencode`, `codex`, `aider` 같은 코딩 어시스턴트를 실행하면 자동으로 Genius Intelligence 와 함께 동작합니다.

설치 방식(고급):

```bash
# 방식을 명시적으로 지정하고 싶을 때만 (기본값은 환경에 맞춰 자동 선택)
curl -fsSL https://senghan1992.github.io/genius_book/install | sh -s -- --mode=pipx
curl -fsSL https://senghan1992.github.io/genius_book/install | sh -s -- --mode=user
curl -fsSL https://senghan1992.github.io/genius_book/install | sh -s -- --mode=global
curl -fsSL https://senghan1992.github.io/genius_book/install | sh -s -- --mode=venv
```

자동 선택 우선순위:
1. `pipx` — 깔끔한 격리 설치, 가장 추천 (있으면 자동 사용)
2. `--user` — sudo 없이 사용자 환경에 설치 (대부분의 Linux/macOS)
3. `venv` — 위 둘이 모두 막힌 시스템(Debian/Ubuntu PEP 668)에서 안전한 fallback

제거:

```bash
curl -fsSL https://senghan1992.github.io/genius_book/install | sh -s -- --uninstall
```

## 핵심 기능

### 1. 플랜 문서 추적 📋 (파일명 무관!)
- **내용 기반 감지**: 파일명이 매번 달라져도(`2024-01-15-refactor.md`, `sprint3-notes.md` 등)
  체크박스·번호 목록·태스크 헤더 같은 **문서 구조**를 분석해 플랜 문서를 자동 인식
- **Planned vs Executed** 비교 분석
- **실행 출력 파싱**: 툴이 플랜 파일을 참조하면 자동 감지

### 2. 자동 지식화
- 3회 이상 반복 시 자동 지식 추출
- 2-depth 그래프 노드
- 30일 미접근 지식 자동 삭제

### 3. 지원 CLI만 감싸기 (32개)

## 플랜 감지 방식 (파일명이 계속 바뀌어도 OK)

파일명 패턴(`CLAUDE.md`, `PLAN.md` 등)은 **보조 힌트**일 뿐이고,
기본 감지 방식은 문서 **내용 구조를 스코어링**하는 것입니다:

| 신호 | 예시 | 가중치 |
|------|------|--------|
| 체크박스 리스트 | `- [ ] 작업 1` | 최대 30 |
| 번호 목록 | `1. 작업 1` | 최대 25 |
| 순차 헤더 | `### 1. 작업`, `### 2. 작업` | 최대 35 |
| 키워드 순차 스텝 | `스텝 1:`, `Step 1:` | 최대 30 |
| 플랜 헤더 키워드 | "계획", "Task", "Plan" 등 | 최대 25 |
| 조합 보너스 | 신호 2개 이상 동시 발생 | +10 |

**예시 - 파일명이 완전히 무작위여도 감지됨:**

```bash
2024-01-15-refactor-notes.md   → ✅ 플랜으로 감지 (체크박스+번호목록)
sprint3-notes-final-v2.md      → ✅ 플랜으로 감지 (순차 헤더 3개)
xk9f-plan-thing.md              → ✅ 플랜으로 감지 (스텝 1/2/3 키워드)
random-notes-abc123.md          → ❌ 일반 메모 (구조 없음, 스킵)
```

### 커스텀 패턴도 추가 가능 (선택사항)

```python
from genius_intelligence import PlanTracker

tracker = PlanTracker(project_root)

# 특정 프로젝트만의 명명 규칙이 있다면 힌트 추가 가능 (필수 아님)
tracker.add_plan_pattern(r"(?i)^my-project-plan\.md$")

# 하지만 기본적으로는 파일명 없이도 동작:
plans = tracker.detect_plan_files()  # 프로젝트 전체를 내용 기반으로 스캔

# 아무 문서나 직접 분석
score = tracker.analyze_any_document("some-random-file.md")
print(score.is_plan, score.score, score.signals)
```

## 플랜 추적 시스템

```
프로젝트 내 모든 .md/.txt 파일 스캔 (파일명 무관)
    ↓
내용 구조 분석 (체크박스, 번호목록, 순차헤더, 키워드)
    ↓
스코어 >= 임계값 → 플랜 문서로 등록
    ↓
태스크 추출
├── [ ] 1. API 서버 구현
├── [ ] 2. DB 설계
└── [ ] 3. 인증 시스템

↓ 실행 추적 (명령/파일/에러 매칭)

├── ✅ 1. API 서버 구현
├── ⚠️ 2. DB 설계 (일부만)
└── ❌ 3. 인증 시스템 (실패)

↓ 비교 분석 & 저장
├── 완료율, 성공률, 해결책, 배운 점
```

## 빠른 시작

```bash
# 한 줄 설치 (질문 없이 끝남)
curl -fsSL https://senghan1992.github.io/genius_book/install | sh

# 새 셸 열기 (PATH 자동 적용)
exec $SHELL

# 코딩 어시스턴트 실행 — Genius 가 자동으로 모든 명령을 추적
claude --no-input
omp
opencode
```

## Python API

```python
from genius_intelligence import PlanTracker

tracker = PlanTracker(project_root)

# 파일명과 무관하게 프로젝트 전체 스캔
plans = tracker.detect_plan_files()

for path in plans:
    score = tracker.analyze_any_document(path)
    plan = tracker.parse_plan_file(path)
    comparison = tracker.compare_plan_vs_execution(plan)
    print(f"{path.name}: 완료율 {comparison['completion_rate']:.0%}")
```

## 저장소 구조

```
.genius_intelligence/
├── memory.sqlite.db
├── plans/                    # 감지된 모든 플랜 (파일명 무관)
│   ├── {id}_refactor-notes.md
│   └── {id}_sprint3-notes.md
├── login_information/
├── knowledge_graph/
└── .config/
```

## 라이선스

MIT License
