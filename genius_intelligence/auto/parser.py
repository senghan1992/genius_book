"""
OutputParser
============
각 코딩 어시스턴트 CLI의 출력 포맷을 파싱하는 모듈

지원 CLI:
- Claude Code: JSON 스트림 + 색상 출력
- OMP: 구조화된 로그
- OpenCode: 일반 텍스트
- Aider: Markdown 포맷
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Iterator, Optional


class OutputParser(ABC):
    """출력 파서 베이스 클래스"""

    @abstractmethod
    def parse(self, output: str, is_error: bool = False) -> list[dict]:
        """출력을 파싱하여 이벤트 목록 반환"""
        ...

    @abstractmethod
    def extract_messages(self, output: str) -> Iterator[tuple[str, str]]:
        """출력에서 사용자/어시스턴트 메시지 추출"""
        ...


class ClaudeCodeParser(OutputParser):
    """Claude Code 출력 파서"""

    def parse(self, output: str, is_error: bool = False) -> list[dict]:
        events = []

        if is_error:
            # Claude Code 에러 포맷
            error_match = re.search(r"Error:?\s*(.+?)(?:\n|$)", output, re.IGNORECASE)
            if error_match:
                events.append({
                    "type": "error",
                    "content": error_match.group(1).strip(),
                    "raw": output[:500],
                })
            elif "traceback" in output.lower():
                events.append({
                    "type": "error",
                    "content": "Traceback detected",
                    "raw": output[:500],
                })
            return events

        # 명령어 실행 감지
        cmd_patterns = [
            r"Running:\s*`(.+?)`",
            r"Running\s+`(.+?)`",
            r"Executing:\s*`(.+?)`",
            r"Executing\s+`(.+?)`",
            r"\$ (.+)",
            r"> (.+)",  # PowerShell
        ]

        for pattern in cmd_patterns:
            match = re.search(pattern, output)
            if match:
                events.append({
                    "type": "command",
                    "content": match.group(1),
                    "success": True,
                })

        # 파일 생성/수정 감지
        file_patterns = [
            r"Wrote\s+(\S+\.(?:py|js|ts|md|json|yaml|yml|html|css))",
            r"Created\s+(\S+\.(?:py|js|ts|md|json|yaml|yml|html|css))",
            r"Modified\s+(\S+\.(?:py|js|ts|md|json|yaml|yml|html|css))",
            r"Updated\s+(\S+\.(?:py|js|ts|md|json|yaml|yml|html|css))",
        ]

        for pattern in file_patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                events.append({
                    "type": "file_changed",
                    "path": match.group(1),
                    "action": pattern.split()[0].lower(),
                })

        # 성공/완료 메시지
        if any(kw in output for kw in ["Done", "Complete", "Finished", "Successfully", "완료", "성공"]):
            events.append({"type": "success", "content": "Task completed"})

        return events

    def extract_messages(self, output: str) -> Iterator[tuple[str, str]]:
        """Claude Code 스트림에서 메시지 추출"""
        # JSON Lines 포맷 시도
        for line in output.split("\n"):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                if "message" in data:
                    role = data.get("type", "assistant")
                    content = data["message"].get("content", "")
                    if content:
                        yield (role, content)
            except json.JSONDecodeError:
                # 일반 텍스트에서 역할 추출
                if "Human:" in line or "User:" in line:
                    yield ("user", line.split(":", 1)[1].strip())
                elif "Assistant:" in line or "Claude:" in line:
                    yield ("assistant", line.split(":", 1)[1].strip())


class OMPParser(OutputParser):
    """OMP (Open Multi-Agent Platform) 출력 파서"""

    def parse(self, output: str, is_error: bool = False) -> list[dict]:
        events = []

        if is_error:
            # OMP 에러 포맷
            error_match = re.search(r"\[ERROR\]\s*(.+)", output)
            if error_match:
                events.append({
                    "type": "error",
                    "content": error_match.group(1).strip(),
                    "raw": output[:500],
                })
            return events

        # OMP 로그 패턴
        patterns = [
            (r"\[CMD\]\s*(.+)", "command"),
            (r"\[FILE\]\s*(.+?)\s+(created|modified|deleted)", "file"),
            (r"\[TOOL\]\s*(.+?)=", "tool_call"),
            (r"\[AGENT\]\s*(.+)", "agent_message"),
            (r"\[STEP\]\s*(.+)", "step"),
        ]

        for pattern, event_type in patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                events.append({
                    "type": event_type,
                    "content": match.group(1).strip() if match.groups() else match.group(0),
                    "raw": output[:300],
                })

        return events

    def extract_messages(self, output: str) -> Iterator[tuple[str, str]]:
        """OMP 메시지 추출"""
        current_role = None
        current_content = []

        for line in output.split("\n"):
            if line.startswith("[AGENT]"):
                if current_role and current_content:
                    yield (current_role, "\\n".join(current_content))
                current_role = "assistant"
                current_content = [line[7:].strip()]
            elif line.startswith("[USER]"):
                if current_role and current_content:
                    yield (current_role, "\\n".join(current_content))
                current_role = "user"
                current_content = [line[6:].strip()]
            elif current_role:
                current_content.append(line)

        if current_role and current_content:
            yield (current_role, "\\n".join(current_content))


class OpenCodeParser(OutputParser):
    """OpenCode 출력 파서"""

    def parse(self, output: str, is_error: bool = False) -> list[dict]:
        events = []

        if is_error:
            events.append({
                "type": "error",
                "content": output[:200],
                "raw": output[:500],
            })
            return events

        # OpenCode 패턴
        patterns = [
            (r"shell:\s*(.+)", "command"),
            (r"file:\s*(.+)", "file"),
            (r"create:\s*(.+)", "file_create"),
            (r"update:\s*(.+)", "file_update"),
            (r"execute:\s*(.+)", "command"),
        ]

        for pattern, event_type in patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                events.append({
                    "type": event_type,
                    "content": match.group(1).strip(),
                })

        return events

    def extract_messages(self, output: str) -> Iterator[tuple[str, str]]:
        """OpenCode 메시지 추출"""
        for block in output.split("\\n\\n"):
            if "User" in block or "user" in block[:20]:
                yield ("user", block.strip())
            elif "Assistant" in block or "assistant" in block[:20]:
                yield ("assistant", block.strip())


class AiderParser(OutputParser):
    """Aider 출력 파서"""

    def parse(self, output: str, is_error: bool = False) -> list[dict]:
        events = []

        if is_error:
            events.append({
                "type": "error",
                "content": output[:200],
                "raw": output[:500],
            })
            return events

        # Aider 패턴
        patterns = [
            (r"git commit\s*-m\s*(.+)", "git_commit"),
            (r"Applied edit to\s+(.+)", "file_modified"),
            (r"Created file\s+(.+)", "file_created"),
            (r"Running:\s*(.+)", "command"),
        ]

        for pattern, event_type in patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                events.append({
                    "type": event_type,
                    "content": match.group(1).strip(),
                })

        return events

    def extract_messages(self, output: str) -> Iterator[tuple[str, str]]:
        """Aider 대화 추출"""
        # Markdown 코드 블록 기반
        in_user = False
        in_assistant = False
        current = []

        for line in output.split("\\n"):
            if "Human:" in line:
                if current:
                    yield ("assistant", "\\n".join(current))
                current = [line.split(":", 1)[1].strip()]
                in_assistant = False
                in_user = True
            elif "Assistant:" in line:
                if current:
                    yield ("user", "\\n".join(current)) if in_user else None
                current = [line.split(":", 1)[1].strip()]
                in_user = False
                in_assistant = True
            elif in_user or in_assistant:
                current.append(line)

        if current:
            yield ("assistant" if in_assistant else "user", "\\n".join(current))


class GenericParser(OutputParser):
    """범용 출력 파서"""

    def parse(self, output: str, is_error: bool = False) -> list[dict]:
        events = []

        # 에러 감지
        if is_error or any(p in output.lower() for p in ["error", "exception", "failed", "fatal"]):
            # 에러 메시지 추출
            error_match = re.search(
                r"(?:Error|Exception|Failed)[:\s]+(.+?)(?:\n|$)",
                output,
                re.IGNORECASE
            )
            events.append({
                "type": "error",
                "content": error_match.group(1)[:200] if error_match else output[:200],
                "raw": output[:500],
            })
            return events

        # 명령어 감지
        cmd_match = re.search(r"\$\s+(.+)", output)
        if cmd_match:
            events.append({
                "type": "command",
                "content": cmd_match.group(1),
                "success": True,
            })

        return events

    def extract_messages(self, output: str) -> Iterator[tuple[str, str]]:
        """범용 메시지 추출"""
        yield ("unknown", output[:500])


# ── 파서 팩토리 ─────────────────────────────────────────────────────

_PARSERS: dict[str, type[OutputParser]] = {
    "claude": ClaudeCodeParser,
    "omp": OMPParser,
    "opencode": OpenCodeParser,
    "aider": AiderParser,
    "generic": GenericParser,
}


def get_parser_for_tool(tool: str) -> OutputParser:
    """도구별 파서 반환"""
    parser_cls = _PARSERS.get(tool.lower(), GenericParser)
    return parser_cls()


def register_parser(tool: str, parser_cls: type[OutputParser]) -> None:
    """커스텀 파서 등록"""
    _PARSERS[tool.lower()] = parser_cls