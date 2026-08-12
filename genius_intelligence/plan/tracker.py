"""
PlanTracker
===========
플랜 문서 추적 및 실행 비교 분석기

1. 플랜 문서 감지 및 파싱
2. 태스크 추출
3. 실행 중 실제 행동 추적
4. Planned vs Executed 비교
5. 실패 분석 및 해결책 기록
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from .types import PlanDocument, PlannedTask, TaskStatus, PlanStatus
from .content_analyzer import PlanContentAnalyzer, PlanScore

logger = logging.getLogger("genius_intelligence")


# ─────────────────────────────────────────────────────────────────
# 툴별 플랜/실행 문서 패턴
# ─────────────────────────────────────────────────────────────────

# Claude Code
CLAUDE_PATTERNS = [
    r"(?i)^CLAUDE\.md$",
    r"(?i)^CLAUDE_WORKSPACE\.md$",
    r"(?i)^\.?CLAUDE/",
    r"(?i)\.claude[_-]?plan",
]

# OMP (Open Multi-Agent Platform)
OMP_PATTERNS = [
    r"(?i)^PLAN\.md$",
    r"(?i)^TASK\.md$",
    r"(?i)^\.?omp[_-]?plan",
    r"(?i)^WORKSPACE\.md$",
    r"(?i)^CONTEXT\.md$",
]

# OpenCode
OPENCODE_PATTERNS = [
    r"(?i)^OPENCODE\.md$",
    r"(?i)^TASKS\.md$",
    r"(?i)^\.?opencode[_-]?plan",
    r"(?i)^AGENT\.md$",
]

# Aider (aider.chat)
AIDER_PATTERNS = [
    r"(?i)^\.?aider[_-]?plan",
    r"(?i)^TODO\.md$",
    r"(?i)^\.?chat[_-]?history",
]

# Codex (OpenAI)
CODEX_PATTERNS = [
    r"(?i)^CODEX\.md$",
    r"(?i)^\.?codex[_-]?plan",
    r"(?i)^SPEC\.md$",
    r"(?i)^\.?openai[_-]?plan",
]

# Cursor
CURSOR_PATTERNS = [
    r"(?i)^\.?cursor[_-]?plan",
    r"(?i)^RULES\.md$",
    r"(?i)^\.?cursor[_-]?rules",
]

# Copilot
COPILOT_PATTERNS = [
    r"(?i)^\.?github[_-]?copilot[_-]?plan",
    r"(?i)^\.?copilot[_-]?instructions",
]

# 범용 플랜 패턴
GENERIC_PATTERNS = [
    r"(?i)^plan\.md$",
    r"(?i)^task[_-]?plan\.md$",
    r"(?i)^todo[_-]?plan\.md$",
    r"(?i)^work[_-]?plan\.md$",
    r"(?i)^execution[_-]?plan\.md$",
    r"(?i)^steps\.md$",
    r"(?i)^tasks\.md$",
    r"(?i)^todo\.md$",
    r"(?i)^\.?genius[_-]?plan",
    r"(?i)^\.?ai[_-]?plan",
]

# 실행 결과/로그 패턴
EXECUTION_PATTERNS = [
    r"(?i)^\.?execution[_-]?log",
    r"(?i)^\.?run[_-]?log",
    r"(?i)^\.?session[_-]?log",
    r"(?i)^\.?genius[_-]?log",
    r"(?i)^\.?output\.md$",
    r"(?i)^\.?result\.md$",
    r"(?i)^\.?summary\.md$",
]

# 툴별 실행 결과 패턴
TOOL_EXECUTION_PATTERNS = {
    "claude": [
        r"(?i)^\.?claude[_-]?history",
        r"(?i)^\.?claude[_-]?session",
    ],
    "omp": [
        r"(?i)^\.?omp[_-]?history",
        r"(?i)^\.?omp[_-]?session",
    ],
    "aider": [
        r"(?i)^\.?aider[_-]?history",
        r"(?i)^\.?aider[_-]?session",
    ],
    "opencode": [
        r"(?i)^\.?opencode[_-]?history",
    ],
}

# 모든 패턴 통합
ALL_PLAN_PATTERNS = (
    CLAUDE_PATTERNS +
    OMP_PATTERNS +
    OPENCODE_PATTERNS +
    AIDER_PATTERNS +
    CODEX_PATTERNS +
    CURSOR_PATTERNS +
    COPILOT_PATTERNS +
    GENERIC_PATTERNS
)

ALL_EXECUTION_PATTERNS = (
    EXECUTION_PATTERNS +
    [p for patterns in TOOL_EXECUTION_PATTERNS.values() for p in patterns]
)

# 툴별 패턴 매핑
TOOL_PATTERNS = {
    "claude": CLAUDE_PATTERNS,
    "omp": OMP_PATTERNS,
    "opencode": OPENCODE_PATTERNS,
    "aider": AIDER_PATTERNS,
    "codex": CODEX_PATTERNS,
    "cursor": CURSOR_PATTERNS,
    "copilot": COPILOT_PATTERNS,
}

# 툴 감지 키워드
TOOL_KEYWORDS = {
    "claude": ["claude", "claude-code", "anthropic"],
    "omp": ["omp", "open multi-agent"],
    "opencode": ["opencode", "open code"],
    "aider": ["aider", "aider-chat"],
    "codex": ["codex", "openai-codex"],
    "cursor": ["cursor", "cursor-ai"],
    "copilot": ["copilot", "github-copilot"],
}

# 툴별 디렉토리
TOOL_DIRECTORIES = {
    "claude": [".claude", ".claude/cache"],
    "omp": [".omp", ".omp/cache"],
    "aider": [".aider", ".aider/cache"],
    "opencode": [".opencode", ".opencode/cache"],
}


class PlanTracker:
    """
    플랜 추적기

    사용법:
        tracker = PlanTracker(project_root)
        tracker.start_monitoring()

        # 플랜 문서 감지
        plans = tracker.detect_plan_files()

        # 플랜 파싱
        plan = tracker.parse_plan_file("CLAUDE.md")

        # 태스크 상태 업데이트
        tracker.update_task_status(plan.id, task_id, "completed", result="...")

        # 비교 분석
        analysis = tracker.compare_plan_vs_execution(plan)

        tracker.stop_monitoring()
    """

    def __init__(
        self,
        project_root: str,
        genius_instance=None,
        custom_plan_patterns: Optional[list[str]] = None,
        custom_execution_patterns: Optional[list[str]] = None,
    ):
        self.project_root = Path(project_root).resolve()
        self.genius = genius_instance

        # 커스텀 패턴 (보조 힌트로 사용, 필수 아님)
        self._custom_plan_patterns = custom_plan_patterns or []
        self._custom_execution_patterns = custom_execution_patterns or []

        # 내용 기반 분석기 (파일명과 무관하게 플랜 문서 판별)
        self.content_analyzer = PlanContentAnalyzer()

        # 이미 스캔한 파일 캐시 (mtime 기준으로 재스캔 방지)
        self._scanned_files: dict[str, float] = {}

        # 추적 중인 플랜
        self.active_plans: dict[str, PlanDocument] = {}

        # 모니터링
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False

        # 마지막 확인 시간
        self._last_check = datetime.now()

        # 이벤트 버퍼
        self._event_buffer: list[dict] = []
        self._buffer_lock = threading.Lock()

    def start_monitoring(self, interval: float = 2.0) -> None:
        """플랜 모니터링 시작"""
        if self._running:
            return

        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval,),
            daemon=True,
        )
        self._monitor_thread.start()
        logger.info("[PlanTracker] Started monitoring")

    def stop_monitoring(self) -> None:
        """플랜 모니터링 중지"""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2)
        logger.info("[PlanTracker] Stopped monitoring")

    def _monitor_loop(self, interval: float) -> None:
        """모니터링 루프"""
        import time
        while self._running:
            try:
                self._check_for_new_plans()
            except Exception as e:
                logger.error(f"[PlanTracker] Monitor error: {e}")
            time.sleep(interval)

    def _check_for_new_plans(self) -> None:
        """
        새 플랜 문서 확인 (백그라운드 폴링)

        mtime 캐시를 사용해 변경되지 않은 파일은 재분석하지 않습니다
        (파일명과 무관하게 내용 기반으로 신규/변경 문서를 계속 탐지).
        """
        scan_results = self.content_analyzer.scan_directory(
            self.project_root,
            mtime_cache=self._scanned_files,
        )

        for path, score in scan_results:
            if not score.is_plan:
                continue

            plan_id = str(path)

            if plan_id not in self.active_plans:
                # 새 플랜 발견 (파일명이 무엇이든 내용으로 감지됨)
                plan = self.parse_plan_file(path)
                if plan:
                    self.active_plans[plan_id] = plan
                    self._on_new_plan(plan)
            else:
                # 이미 추적 중인 플랜의 내용이 변경됨 → 재파싱하여 갱신
                self._refresh_plan(plan_id, path)

    def _refresh_plan(self, plan_id: str, path: Path) -> None:
        """기존에 추적 중인 플랜 문서가 수정되었을 때 태스크 목록을 갱신"""
        try:
            content_text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return

        old_plan = self.active_plans[plan_id]
        new_tasks = self._extract_tasks(content_text)

        # 기존 태스크와 제목이 같으면 상태/진행도를 유지하고,
        # 새로 추가된 태스크만 반영 (완전히 새로 덮어쓰지 않음)
        existing_titles = {t.title: t for t in old_plan.parsed_tasks}
        merged_tasks = []
        for new_task in new_tasks:
            if new_task.title in existing_titles:
                merged_tasks.append(existing_titles[new_task.title])
            else:
                merged_tasks.append(new_task)

        old_plan.parsed_tasks = merged_tasks
        old_plan.raw_content = content_text
        old_plan.recalculate_stats()

    # ── 플랜 감지 ─────────────────────────────────────────────────

    def get_all_patterns(self) -> list[str]:
        """모든 활성 패턴 반환 (기본 + 커스텀, 힌트용)"""
        return ALL_PLAN_PATTERNS + self._custom_plan_patterns

    def get_all_execution_patterns(self) -> list[str]:
        """모든 실행 패턴 반환 (기본 + 커스텀, 힌트용)"""
        return ALL_EXECUTION_PATTERNS + self._custom_execution_patterns

    def add_plan_pattern(self, pattern: str) -> None:
        """커스텀 플랜 파일명 패턴 추가 (정규식, 보조 힌트)"""
        self._custom_plan_patterns.append(pattern)

    def add_execution_pattern(self, pattern: str) -> None:
        """커스텀 실행 파일명 패턴 추가 (정규식, 보조 힌트)"""
        self._custom_execution_patterns.append(pattern)

    def detect_plan_files(
        self,
        tool: Optional[str] = None,
        use_content_analysis: bool = True,
        min_score: Optional[float] = None,
    ) -> list[Path]:
        """
        프로젝트에서 플랜 문서 파일 감지

        핵심: 파일명은 프로젝트/툴마다 자유롭게 바뀔 수 있으므로
        (예: 2024-01-15-refactor.md, sprint3-tasks.md 등),
        기본적으로 "문서 내용"을 분석해서 플랜 여부를 판단합니다.
        파일명 패턴은 스코어를 보정하는 보조 힌트로만 사용됩니다.

        Args:
            tool: 특정 툴명 (claude, omp, opencode 등) - 힌트로 사용
            use_content_analysis: True면 내용 기반 분석 사용 (기본값, 권장)
                                   False면 파일명 패턴 매칭만 사용 (레거시)
            min_score: 플랜으로 판단할 최소 스코어 (기본: PlanContentAnalyzer.PLAN_THRESHOLD)
        """
        if use_content_analysis:
            return self._detect_plan_files_by_content(tool=tool, min_score=min_score)
        return self._detect_plan_files_by_filename(tool=tool)

    def _detect_plan_files_by_content(
        self,
        tool: Optional[str] = None,
        min_score: Optional[float] = None,
    ) -> list[Path]:
        """
        내용 기반 플랜 문서 감지 (파일명 무관)

        프로젝트 내 모든 텍스트/마크다운 파일을 스캔하여
        체크박스, 번호 목록, 태스크 헤더 등 구조적 신호로 스코어링합니다.
        """
        threshold = min_score if min_score is not None else self.content_analyzer.PLAN_THRESHOLD

        scan_results = self.content_analyzer.scan_directory(self.project_root)

        found = []
        for path, score in scan_results:
            if not score.is_plan or score.score < threshold:
                continue

            # 툴 필터 (선택적 - 파일명/경로에 툴 힌트가 있으면 우선)
            if tool:
                if not self._matches_tool_hint(path, tool):
                    # 툴 힌트가 명시적으로 다른 툴을 가리키면 스킵하지 않고
                    # 그냥 점수만 낮게 취급 (완전히 배제하지 않음 - 유연성 유지)
                    pass

            found.append(path)

        # 최신 순 정렬
        found = sorted(set(found), key=lambda p: p.stat().st_mtime, reverse=True)
        return found

    def _detect_plan_files_by_filename(self, tool: Optional[str] = None) -> list[Path]:
        """
        (레거시/보조) 파일명 패턴 기반 플랜 문서 감지

        내용 분석이 불가능한 상황(예: 매우 큰 파일, 바이너리 등)의
        fallback 이나, 알려진 툴의 고정 파일명을 빠르게 찾을 때 사용.
        """
        found = []

        if tool:
            tool_lower = tool.lower()
            patterns = []
            for t, keywords in TOOL_KEYWORDS.items():
                if tool_lower in [t] + keywords:
                    patterns.extend(TOOL_PATTERNS.get(t, []))
                    break
            if not patterns:
                patterns = ALL_PLAN_PATTERNS
        else:
            patterns = ALL_PLAN_PATTERNS

        patterns = patterns + self._custom_plan_patterns
        patterns = list(set(patterns))

        for pattern in patterns:
            for match in self.project_root.rglob("*"):
                if match.is_file() and re.match(pattern, match.name):
                    found.append(match)

        found = sorted(set(found), key=lambda p: p.stat().st_mtime, reverse=True)
        return found

    def _matches_tool_hint(self, path: Path, tool: str) -> bool:
        """파일 경로/이름에 특정 툴의 힌트가 있는지 확인 (약한 신호)"""
        tool_lower = tool.lower()
        path_str = str(path).lower()
        keywords = TOOL_KEYWORDS.get(tool_lower, [tool_lower])
        return any(kw in path_str for kw in keywords)

    def analyze_any_document(self, file_path: str | Path) -> Optional[PlanScore]:
        """
        임의의 문서를 분석하여 플랜/실행 문서 여부와 스코어 반환

        파일명이 무엇이든 상관없이 내용만으로 판단합니다.
        """
        return self.content_analyzer.analyze_file(file_path)


    def detect_execution_files(self, tool: Optional[str] = None) -> list[Path]:
        """
        프로젝트에서 실행 결과/로그 파일 감지
        """
        found = []

        if tool and tool in TOOL_EXECUTION_PATTERNS:
            patterns = TOOL_EXECUTION_PATTERNS[tool]
        else:
            patterns = ALL_EXECUTION_PATTERNS

        for pattern in patterns:
            for match in self.project_root.rglob("*"):
                if match.is_file() and re.match(pattern, match.name):
                    found.append(match)

        found = sorted(set(found), key=lambda p: p.stat().st_mtime, reverse=True)
        return found

    def detect_tool_from_files(self) -> Optional[str]:
        """
        프로젝트 내 파일명으로부터 사용된 툴 추측
        """
        all_files = list(self.project_root.rglob("*"))
        file_names = [f.name.lower() for f in all_files if f.is_file()]

        scores = {}
        for tool, keywords in TOOL_KEYWORDS.items():
            score = 0
            for kw in keywords:
                for name in file_names:
                    if kw in name:
                        score += 1
            if score > 0:
                scores[tool] = score

        if scores:
            return max(scores, key=scores.get)
        return None

    def on_output_line(self, line: str, tool: Optional[str] = None) -> Optional[Path]:
        """
        CLI 출력 라인을 분석하여 플랜 파일 참조 감지

        Returns:
            감지된 플랜 파일 경로 또는 None
        """
        # 패턴: "Created PLAN.md", "Writing to CLAUDE.md", "Read CLAUDE.md"
        plan_ref_patterns = [
            r"(?:created|writing|reading|opened|loaded|updated)\s+([\w\-./]+\.md)",
            r"(?:using|follows?)\s+plan\s+from\s+([\w\-./]+\.md)",
            r"plan[:\s]+([\w\-./]+\.md)",
            r"loaded\s+([\w\-./]+\.md)\s+as\s+context",
        ]

        for pattern in plan_ref_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                filename = match.group(1)
                # 상대 경로 또는 파일명
                if filename.startswith("/"):
                    path = Path(filename)
                else:
                    path = self.project_root / filename

                # 파일 존재 확인
                if path.exists() and self.is_plan_file(path.name):
                    # 새 플랜으로 등록
                    if str(path) not in self.active_plans:
                        plan = self.parse_plan_file(path)
                        if plan:
                            plan.created_by = tool or "unknown"
                            self.active_plans[str(path)] = plan
                            logger.info(f"[PlanTracker] Detected from output: {path.name}")
                            return path

        return None

    def is_plan_file(self, file_path: str | Path, use_content_analysis: bool = True) -> bool:
        """
        해당 파일이 플랜 문서인지 확인

        기본적으로 내용 기반 분석을 사용 (파일명 무관).
        use_content_analysis=False로 지정하면 파일명 패턴만 확인 (레거시).
        """
        path = Path(file_path)

        if use_content_analysis and path.exists():
            score = self.content_analyzer.analyze_file(path)
            if score is not None:
                return score.is_plan

        # Fallback: 파일명 패턴 (파일이 없거나 분석 불가한 경우)
        all_patterns = self.get_all_patterns()
        for pattern in all_patterns:
            if re.match(pattern, path.name):
                return True
        return False

    def is_execution_file(self, file_path: str | Path, use_content_analysis: bool = True) -> bool:
        """
        해당 파일이 실행 결과 문서인지 확인

        기본적으로 내용 기반 분석을 사용 (파일명 무관).
        """
        path = Path(file_path)

        if use_content_analysis and path.exists():
            score = self.content_analyzer.analyze_file(path)
            if score is not None:
                return score.is_execution_doc

        for pattern in ALL_EXECUTION_PATTERNS:
            if re.match(pattern, path.name):
                return True
        return False

    # ── 플랜 파싱 ─────────────────────────────────────────────────

    def parse_plan_file(self, file_path: str | Path) -> Optional[PlanDocument]:
        """플랜 파일 파싱"""
        path = Path(file_path)

        if not path.exists():
            return None

        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"[PlanTracker] Failed to read {path}: {e}")
            return None

        # PlanDocument 생성
        plan = PlanDocument(
            title=self._extract_title(content, path.name),
            description=self._extract_description(content),
            source=str(path.relative_to(self.project_root)),
            source_type=path.suffix.lstrip("."),
            raw_content=content,
            file_path=str(path),
        )

        # 태스크 추출
        tasks = self._extract_tasks(content)
        plan.parsed_tasks = tasks
        plan.total_tasks = len(tasks)

        # 상태 설정
        if tasks:
            plan.status = PlanStatus.ACTIVE
        else:
            plan.status = PlanStatus.DRAFT

        return plan

    def _extract_title(self, content: str, filename: str) -> str:
        """제목 추출"""
        # 첫 번째 # 제목
        match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if match:
            return match.group(1).strip()

        # 파일명에서 추출
        name = Path(filename).stem
        name = re.sub(r"[_-]", " ", name)
        return name.title()

    def _extract_description(self, content: str) -> str:
        """설명 추출 (첫 번째 문단)"""
        lines = content.split("\n")
        desc_lines = []
        started = False

        for line in lines:
            line = line.strip()
            if line.startswith("#"):
                if started:
                    break
                continue
            if line:
                desc_lines.append(line)
                started = True
            elif started and desc_lines:
                break

        return " ".join(desc_lines)[:200]

    def _extract_tasks(self, content: str) -> list[PlannedTask]:
        """마크다운에서 태스크 추출

        - 헤더는 Task/Step/계획/작업 등 키워드가 포함된 경우만 태스크로 한정
        - [x] 체크박스는 is_completed=True 세팅 (completion_rate가 0이 되는 버그 수정)
        - 코드 블록 안의 번호 리스트는 제외
        """
        tasks = []
        current_task = None
        in_code_block = False

        lines = content.split("\n")

        for line in lines:
            line = line.strip()

            # 코드 블록 토글
            if line.startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue

            # 체크박스 태스크
            checkbox_match = re.match(r"^[-*]\s+\[([ xX])\]\s+(.+)$", line)
            if checkbox_match:
                if current_task:
                    tasks.append(current_task)
                check = checkbox_match.group(1).lower()
                title = checkbox_match.group(2).strip()
                is_done = check == "x"
                task = PlannedTask(
                    title=title,
                    order=len(tasks),
                    status=TaskStatus.COMPLETED if is_done else TaskStatus.PLANNED,
                )
                if is_done:
                    task.is_completed = True
                    task.completion_rate = 1.0
                current_task = task
                continue

            # 번호 리스트 태스크
            numbered_match = re.match(r"^\d+[.)]\s+(.+)$", line)
            if numbered_match:
                if current_task:
                    tasks.append(current_task)
                title = numbered_match.group(1).strip()
                current_task = PlannedTask(
                    title=title,
                    order=len(tasks),
                    status=TaskStatus.PLANNED,
                )
                continue

            # 헤더 태스크: Task/Step/계획/작업/단계/할일 키워드가 포함된 헤더만
            header_kw_pattern = r"^(?:Task|Step|Todo|작업|단계|계획|할일|진행|실행|Phase|Sprint|Milestone)"
            header_match = re.match(
                r"^#{2,4}\s+(?:\d+\.?\s*)?" + header_kw_pattern + r"[:\-]?\s*(.+)?$",
                line, re.IGNORECASE
            )
            if header_match:
                if current_task:
                    tasks.append(current_task)
                title = header_match.group(1) or f"Task {len(tasks) + 1}"
                current_task = PlannedTask(
                    title=title.strip(),
                    order=len(tasks),
                    status=TaskStatus.PLANNED,
                )
                continue

            # 현재 태스크에 설명 추가
            if current_task and line and not line.startswith("#"):
                if current_task.description:
                    current_task.description += " " + line
                else:
                    current_task.description = line

        if current_task:
            tasks.append(current_task)

        return tasks

    # ── 실행 추적 ─────────────────────────────────────────────────

    def on_command_executed(self, command: str, success: bool = True,
                           output: str = "", error: str = "") -> None:
        """실행된 명령어 기록"""
        with self._buffer_lock:
            self._event_buffer.append({
                "type": "command",
                "content": command,
                "success": success,
                "output": output,
                "error": error,
                "timestamp": datetime.now().isoformat(),
            })

        self._match_command_to_tasks(command, success)

    def on_file_created(self, file_path: str) -> None:
        """생성된 파일 기록"""
        with self._buffer_lock:
            self._event_buffer.append({
                "type": "file",
                "action": "created",
                "path": file_path,
                "timestamp": datetime.now().isoformat(),
            })

        self._match_file_to_tasks(file_path, "created")

    def on_file_modified(self, file_path: str) -> None:
        """수정된 파일 기록"""
        with self._buffer_lock:
            self._event_buffer.append({
                "type": "file",
                "action": "modified",
                "path": file_path,
                "timestamp": datetime.now().isoformat(),
            })

        self._match_file_to_tasks(file_path, "modified")

    def on_error(self, error: str, context: str = "") -> None:
        """에러 기록"""
        with self._buffer_lock:
            self._event_buffer.append({
                "type": "error",
                "content": error,
                "context": context,
                "timestamp": datetime.now().isoformat(),
            })

        self._match_error_to_tasks(error)

    # ── 태스크 매칭 ───────────────────────────────────────────────

    def _match_command_to_tasks(self, command: str, success: bool) -> None:
        """실행된 명령어를 플랜 태스크와 매칭

        한 번의 무관 명령으로 태스크가 닫히지 않게:
        - stopword 필터 (git, cd, ls, echo, cat 등)
        - 명령-태스크 단어 교집합 2개 이상 (정밀 일치)
        - success=True여도 즉시 완료하지 않고 started 상태로만 표시
        """
        if not self.active_plans:
            return

        command_lower = command.lower()

        # stopword — 이런 명령은 태스크 완료로 간주하지 않음
        stopword_cmds = {"git", "cd", "ls", "echo", "cat", "pwd", "export",
                         "mv", "cp", "rm", "mkdir", "touch", "chmod"}
        cmd_tokens = command_lower.split()
        if cmd_tokens and cmd_tokens[0] in stopword_cmds:
            return

        for plan_id, plan in self.active_plans.items():
            for task in plan.parsed_tasks:
                if task.status not in (TaskStatus.PLANNED, TaskStatus.IN_PROGRESS):
                    continue

                # 명령어와 태스크 제목 유사성 체크 (정밀 일치)
                task_words = set(task.title.lower().split())
                cmd_words = set(command_lower.split())

                # stopword 제거 후 의미있는 단어만 비교
                stopword_words = {"the", "a", "an", "to", "for", "in", "on",
                                  "with", "and", "or", "of", "is", "are"}
                task_meaningful = task_words - stopword_words
                cmd_meaningful = cmd_words - stopword_words

                common = task_meaningful & cmd_meaningful
                # 2개 이상 공통 단어가 있으면 매칭 (즉시 완료하지 않음)
                if len(common) >= 2 or (len(common) >= 1 and len(task_meaningful) <= 2):
                    if not task.started_at:
                        task.mark_started()
                    task.actual_action = command
                    # success=True여도 즉시 완료하지 않음 —
                    # 한 번의 명령으로 태스크가 닫히지 않게.
                    # 실패한 경우에만 mark_failed
                    if not success:
                        task.mark_failed(f"Command failed: {command}")

                    plan.recalculate_stats()
                    self._check_plan_completion(plan)

    def _match_file_to_tasks(self, file_path: str, action: str) -> None:
        """파일 변경을 플랜 태스크와 매칭"""
        if not self.active_plans:
            return

        filename = Path(file_path).name
        filename_lower = filename.lower()

        for plan_id, plan in self.active_plans.items():
            for task in plan.parsed_tasks:
                if task.status not in (TaskStatus.PLANNED, TaskStatus.IN_PROGRESS):
                    continue

                # 파일명과 태스크 유사성 체크
                if filename_lower in task.title.lower() or \
                   task.title.lower() in filename_lower:
                    if not task.started_at:
                        task.mark_started()

                    task.files.append(file_path)
                    task.actual_action = f"{action}: {file_path}"

                    # 읽기/쓰기 명령 관련이면 완료 처리
                    if any(kw in file_path.lower() for kw in [".py", ".js", ".ts", ".go", ".rs"]):
                        task.mark_completed(f"File {action}: {filename}")

                    plan.recalculate_stats()
                    self._check_plan_completion(plan)

    def _match_error_to_tasks(self, error: str) -> None:
        """에러를 관련 태스크와 매칭"""
        if not self.active_plans:
            return

        error_lower = error.lower()

        for plan_id, plan in self.active_plans.items():
            for task in plan.parsed_tasks:
                if task.status == TaskStatus.IN_PROGRESS:
                    # 현재 진행 중인 태스크에 에러 연결
                    if not task.error:
                        task.mark_failed(error)
                        plan.recalculate_stats()

    def _check_plan_completion(self, plan: PlanDocument) -> None:
        """플랜 완료 상태 확인"""
        if plan.completed_tasks == plan.total_tasks:
            plan.status = PlanStatus.COMPLETED
            plan.completed_at = datetime.now()
        elif plan.failed_tasks > 0 or plan.skipped_tasks > 0:
            if plan.completion_rate >= 0.5:
                plan.status = PlanStatus.PARTIAL
            else:
                plan.status = PlanStatus.FAILED
        elif plan.completed_tasks > 0:
            plan.status = PlanStatus.ACTIVE

    # ── 업데이트 ──────────────────────────────────────────────────

    def update_task_status(
        self,
        plan_id: str,
        task_id: str,
        status: str,
        result: str = "",
        error: str = "",
        notes: str = "",
    ) -> None:
        """수동으로 태스크 상태 업데이트"""
        if plan_id not in self.active_plans:
            return

        plan = self.active_plans[plan_id]

        for task in plan.parsed_tasks:
            if task.id == task_id:
                if status == "completed":
                    task.mark_completed(result)
                elif status == "failed":
                    task.mark_failed(error or notes)
                elif status == "skipped":
                    task.mark_skipped(notes)
                elif status == "in_progress":
                    task.mark_started()

                plan.recalculate_stats()
                self._check_plan_completion(plan)
                break

    def add_workaround(self, plan_id: str, workaround: str) -> None:
        """해결책 추가"""
        if plan_id in self.active_plans:
            self.active_plans[plan_id].workarounds.append(workaround)

    def add_learning(self, plan_id: str, learning: str) -> None:
        """배운 점 추가"""
        if plan_id in self.active_plans:
            self.active_plans[plan_id].learnings.append(learning)

    def add_execution_note(self, plan_id: str, note: str) -> None:
        """실행 메모 추가"""
        if plan_id in self.active_plans:
            plan = self.active_plans[plan_id]
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            plan.execution_notes += f"[{timestamp}] {note}\\n"

    # ── 저장 ────────────────────────────────────────────────────

    def save_plan(self, plan: PlanDocument) -> str:
        """플랜 저장"""
        # 디렉토리 생성
        plans_dir = self.project_root / ".genius_intelligence" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)

        # 파일 저장
        filename = f"{plan.id[:8]}_{Path(plan.source).stem}.md"
        file_path = plans_dir / filename

        content = plan.to_markdown()
        file_path.write_text(content, encoding="utf-8")

        plan.file_path = str(file_path.relative_to(self.project_root))

        # DB 저장 (GeniusIntelligence 연결)
        if self.genius:
            self._save_plan_to_db(plan)

        logger.info(f"[PlanTracker] Saved plan: {filename}")
        return str(file_path)

    def _save_plan_to_db(self, plan: PlanDocument) -> None:
        """플랜을 DB에 저장"""
        # plans 테이블이 없으면 생성
        try:
            with self.genius.db._conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS plan_documents (
                        id TEXT PRIMARY KEY,
                        title TEXT,
                        description TEXT,
                        source TEXT,
                        status TEXT,
                        total_tasks INTEGER,
                        completed_tasks INTEGER,
                        failed_tasks INTEGER,
                        raw_content TEXT,
                        file_path TEXT,
                        created_at TEXT,
                        updated_at TEXT,
                        completed_at TEXT,
                        workarounds TEXT,
                        learnings TEXT
                    )
                """)

                conn.execute("""
                    INSERT OR REPLACE INTO plan_documents
                    (id, title, description, source, status, total_tasks,
                     completed_tasks, failed_tasks, raw_content, file_path,
                     created_at, updated_at, completed_at, workarounds, learnings)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    plan.id,
                    plan.title,
                    plan.description,
                    plan.source,
                    plan.status.value,
                    plan.total_tasks,
                    plan.completed_tasks,
                    plan.failed_tasks,
                    plan.raw_content[:5000],
                    plan.file_path,
                    plan.created_at.isoformat(),
                    plan.updated_at.isoformat(),
                    plan.completed_at.isoformat() if plan.completed_at else None,
                    json.dumps(plan.workarounds),
                    json.dumps(plan.learnings),
                ))
        except Exception as e:
            logger.error(f"[PlanTracker] Failed to save plan to DB: {e}")

    # ── 이벤트 ───────────────────────────────────────────────────

    def _on_new_plan(self, plan: PlanDocument) -> None:
        """새 플랜 발견 이벤트"""
        logger.info(f"[PlanTracker] New plan detected: {plan.title}")

        if self.genius and self.genius.current_session:
            from ..types.session import SessionEvent, EventType
            event = SessionEvent(
                event_type=EventType.USER_MESSAGE,
                content=f"Plan detected: {plan.title}",
                event_metadata={"plan_id": plan.id, "source": plan.source},
            )
            self.genius.current_session.add_event(event)

    # ── 유틸리티 ─────────────────────────────────────────────────

    def get_active_plans(self) -> list[PlanDocument]:
        """활성 플랜 목록"""
        return list(self.active_plans.values())

    def get_plan_summary(self) -> dict:
        """플랜 요약"""
        plans = self.get_active_plans()
        return {
            "total_plans": len(plans),
            "active": sum(1 for p in plans if p.status == PlanStatus.ACTIVE),
            "completed": sum(1 for p in plans if p.status == PlanStatus.COMPLETED),
            "partial": sum(1 for p in plans if p.status == PlanStatus.PARTIAL),
            "failed": sum(1 for p in plans if p.status == PlanStatus.FAILED),
        }

    def compare_plan_vs_execution(self, plan: PlanDocument) -> dict:
        """Planned vs Executed 비교 분석"""
        comparison = {
            "plan_id": plan.id,
            "title": plan.title,
            "total_tasks": plan.total_tasks,
            "completed": plan.completed_tasks,
            "failed": plan.failed_tasks,
            "skipped": plan.skipped_tasks,
            "completion_rate": plan.completion_rate,
            "success_rate": plan.success_rate,
            "task_details": [],
        }

        for task in plan.parsed_tasks:
            task_info = {
                "id": task.id,
                "title": task.title,
                "planned": True,
                "started": task.started_at is not None,
                "completed": task.is_completed,
                "actual_action": task.actual_action,
                "result": task.result,
                "error": task.error,
                "files": task.files,
                "status": task.status.value,
            }
            comparison["task_details"].append(task_info)

        return comparison