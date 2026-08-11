"""
PlanContentAnalyzer
===================
파일명이 아닌 "문서 내용/구조"를 분석하여 플랜 문서인지 판단

파일명은 프로젝트/툴마다 자유롭게 바뀔 수 있으므로(예: 2024-01-15-refactor.md,
sprint3-tasks.md, feature-x-plan.md 등), 파일명 패턴 매칭에만 의존하지 않고
문서 내부 구조(체크박스, 번호 목록, 태스크 헤더, 순차적 스텝 등)를 스코어링해서
"이 문서가 플랜/태스크 문서일 확률"을 계산합니다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# 플랜스러움을 나타내는 헤더 키워드 (다국어)
PLAN_HEADER_KEYWORDS = [
    # 한국어
    "계획", "작업", "단계", "태스크", "할일", "진행", "실행",
    # 영어
    "plan", "task", "step", "todo", "to-do", "roadmap",
    "milestone", "checklist", "action item", "next step",
    "implementation", "phase", "sprint", "backlog",
]

# 실행/결과 문서를 나타내는 키워드
EXECUTION_HEADER_KEYWORDS = [
    "결과", "실행 로그", "완료", "요약", "리포트", "회고",
    "result", "execution log", "summary", "report", "outcome",
    "retrospective", "session log", "run log", "changelog",
]

# 텍스트 전반에서 플랜스러움을 암시하는 키워드
PLAN_BODY_KEYWORDS = [
    "구현할", "진행할", "예정", "계획", "순서대로",
    "implement", "will do", "next", "step by step", "todo",
    "planned", "scheduled", "upcoming",
]


@dataclass
class PlanScore:
    """플랜 문서 스코어링 결과"""
    score: float = 0.0
    is_plan: bool = False
    is_execution_doc: bool = False
    signals: list[str] = field(default_factory=list)
    checkbox_count: int = 0
    numbered_step_count: int = 0
    task_header_count: int = 0


class PlanContentAnalyzer:
    """
    문서 내용 기반 플랜 판별기

    파일명에 의존하지 않고, 다음 신호들을 조합해 스코어링합니다:
      - 체크박스 리스트 (- [ ], - [x])
      - 번호가 붙은 순차 스텝 (1. 2. 3. ...)
      - "Task/Step/계획/작업" 등 헤더 키워드
      - 순차적인 헤더 구조 (### 1, ### 2, ### 3 ...)
      - 본문 내 플랜스러운 표현

    사용법:
        analyzer = PlanContentAnalyzer()
        result = analyzer.analyze(text)
        if result.is_plan:
            ...
    """

    # 임계값 (이 이상이면 플랜 문서로 판단)
    PLAN_THRESHOLD = 35.0
    EXECUTION_THRESHOLD = 25.0

    def analyze(self, content: str, filename: str = "") -> PlanScore:
        """문서 내용을 분석하여 플랜스러움 스코어링"""
        score = 0.0
        signals = []

        # 1. 체크박스 리스트
        checkbox_matches = re.findall(r"^\s*[-*]\s+\[[ xX]\]\s+.+$", content, re.MULTILINE)
        checkbox_count = len(checkbox_matches)
        if checkbox_count >= 1:
            add = min(30, checkbox_count * 8)
            score += add
            signals.append(f"checkbox_list(x{checkbox_count})")

        # 2. 번호가 붙은 순차 스텝 (1. xxx / 1) xxx)
        numbered_matches = re.findall(r"^\s*\d+[.)]\s+.+$", content, re.MULTILINE)
        numbered_count = len(numbered_matches)
        if numbered_count >= 2:
            add = min(25, numbered_count * 5)
            score += add
            signals.append(f"numbered_steps(x{numbered_count})")

        # 2b. "스텝 1:", "Step 1:", "단계 1:" 같은 콜론/키워드 기반 순차 스텝
        # (마크다운 리스트/헤더가 아닌 일반 텍스트 줄에도 대응)
        keyword_step_matches = re.findall(
            r"(?im)^\s*(?:step|스텝|단계|task|태스크)\s*\d+\s*[:.)\-]",
            content,
        )
        keyword_step_count = len(keyword_step_matches)
        if keyword_step_count >= 2:
            add = min(30, keyword_step_count * 10)
            score += add
            signals.append(f"keyword_numbered_steps(x{keyword_step_count})")

        # 3. 순차적인 헤더 구조 (### 1. xxx, ### 2. xxx 등)
        # 3개 이상 연속된 번호 헤더는 태스크 목록일 확률이 매우 높으므로 가중치 상향
        seq_header_matches = re.findall(
            r"^#{1,4}\s*\d+[.)]?\s+.+$", content, re.MULTILINE
        )
        seq_count = len(seq_header_matches)
        if seq_count >= 2:
            add = min(35, seq_count * 10)
            score += add
            signals.append(f"sequential_headers(x{seq_count})")

        # 4. 플랜 관련 헤더 키워드
        task_header_count = 0
        for line in content.split("\n"):
            if re.match(r"^#{1,4}\s+", line):
                line_lower = line.lower()
                for kw in PLAN_HEADER_KEYWORDS:
                    if kw in line_lower:
                        task_header_count += 1
                        break
        if task_header_count >= 1:
            add = min(25, task_header_count * 8)
            score += add
            signals.append(f"plan_header_keywords(x{task_header_count})")

        # 5. 본문 내 플랜스러운 표현
        body_hits = sum(1 for kw in PLAN_BODY_KEYWORDS if kw in content.lower())
        if body_hits >= 1:
            add = min(10, body_hits * 3)
            score += add
            signals.append(f"plan_body_keywords(x{body_hits})")

        # 6. 파일명 힌트 (보조 신호, 필수 아님)
        if filename:
            filename_lower = filename.lower()
            filename_hint_kws = [
                "plan", "task", "todo", "step", "spec", "roadmap",
                "계획", "작업", "태스크",
            ]
            if any(kw in filename_lower for kw in filename_hint_kws):
                score += 10
                signals.append("filename_hint")

        # 실행/결과 문서 스코어
        exec_score = 0.0
        exec_header_count = 0
        for line in content.split("\n"):
            if re.match(r"^#{1,4}\s+", line):
                line_lower = line.lower()
                for kw in EXECUTION_HEADER_KEYWORDS:
                    if kw in line_lower:
                        exec_header_count += 1
                        break
        if exec_header_count >= 1:
            exec_score += min(25, exec_header_count * 10)

        # 완료/실패 마커가 많으면 실행 문서일 확률 상승
        done_markers = len(re.findall(r"(✅|❌|⚠️|\[x\]|완료|실패|success|failed|done)", content, re.IGNORECASE))
        if done_markers >= 3:
            exec_score += 15

        # 조합 보너스: 서로 다른 구조적 신호가 2개 이상 동시에 나타나면
        # (예: 체크박스 + 번호목록, 순차헤더 + 키워드헤더 등) 단일 신호보다
        # 훨씬 강한 "플랜 문서" 증거이므로 소폭 가중치를 더해줍니다.
        structural_signal_types = sum([
            checkbox_count >= 1,
            numbered_count >= 2,
            len(seq_header_matches) >= 2,
            keyword_step_count >= 2,
            task_header_count >= 1,
        ])
        if structural_signal_types >= 2:
            score += 10
            signals.append(f"combo_bonus(x{structural_signal_types}_signal_types)")

        result = PlanScore(
            score=score,
            is_plan=score >= self.PLAN_THRESHOLD,
            is_execution_doc=exec_score >= self.EXECUTION_THRESHOLD,
            signals=signals,
            checkbox_count=checkbox_count,
            numbered_step_count=numbered_count,
            task_header_count=task_header_count,
        )
        return result

    def analyze_file(self, file_path: str | Path) -> Optional[PlanScore]:
        """파일을 읽어서 분석"""
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            return None

        # 텍스트 파일만 분석 (마크다운/텍스트 위주)
        if path.suffix.lower() not in (".md", ".markdown", ".txt", ".rst"):
            return None

        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return None

        return self.analyze(content, filename=path.name)

    def scan_directory(
        self,
        root: str | Path,
        max_files: int = 500,
        exclude_dirs: Optional[set[str]] = None,
        mtime_cache: Optional[dict[str, float]] = None,
    ) -> list[tuple[Path, PlanScore]]:
        """
        디렉토리를 스캔하여 플랜스러운 문서들을 내용 기반으로 찾음
        (파일명과 무관하게 동작)

        Args:
            mtime_cache: {파일경로: 마지막 수정시간} 캐시. 제공하면
                         변경되지 않은 파일은 재분석하지 않고 이전 결과를 씁니다
                         (반복 폴링 시 성능 개선). 캐시는 in-place로 갱신됩니다.
        """
        exclude_dirs = exclude_dirs or {
            ".git", "node_modules", "__pycache__", ".venv", "venv",
            ".genius_intelligence", "dist", "build", ".next", ".cache",
        }

        root_path = Path(root)
        results = []
        checked = 0

        for path in root_path.rglob("*"):
            if checked >= max_files:
                break

            # 제외 디렉토리 스킵
            if any(part in exclude_dirs for part in path.parts):
                continue

            if not path.is_file():
                continue

            if path.suffix.lower() not in (".md", ".markdown", ".txt", ".rst"):
                continue

            checked += 1

            # mtime 캐시 체크 (변경 없으면 스킵하되, 이전 결과 유지 안 함 -
            # 호출자가 active_plans에 이미 반영했으므로 여기서는 스킵만)
            if mtime_cache is not None:
                try:
                    mtime = path.stat().st_mtime
                except OSError:
                    continue
                cache_key = str(path)
                if mtime_cache.get(cache_key) == mtime:
                    continue
                mtime_cache[cache_key] = mtime

            score = self.analyze_file(path)
            if score and (score.is_plan or score.is_execution_doc):
                results.append((path, score))

        # 스코어 높은 순으로 정렬
        results.sort(key=lambda x: x[1].score, reverse=True)
        return results