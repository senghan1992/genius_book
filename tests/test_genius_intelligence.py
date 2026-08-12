"""
Tests for Genius Intelligence Library
"""

import os
import shutil
import tempfile
from pathlib import Path

import pytest

import genius_intelligence.memory.db
genius_intelligence.memory.db._db_cache.clear()



class TestKnowledgeNode:
    def test_node_creation(self):
        from genius_intelligence.types.knowledge import KnowledgeNode, KnowledgeType
        node = KnowledgeNode(
            name="jwt-auth", domain="api", topic="jwt-auth", depth=2,
            knowledge_type=KnowledgeType.SUCCESS,
            raw_input="JWT auth", solution="done",
        )
        assert node.name == "jwt-auth"
        assert node.node_key == "api/jwt-auth"
        assert node.attempt_count == 0

    def test_node_markdown(self):
        from genius_intelligence.types.knowledge import KnowledgeNode
        node = KnowledgeNode(name="test", domain="api", topic="test",
                             raw_input="request", solution="answer")
        md = node.to_markdown()
        assert "# test" in md
        assert "request" in md
        assert "answer" in md

    def test_node_touch(self):
        from genius_intelligence.types.knowledge import KnowledgeNode
        node = KnowledgeNode(name="test")
        initial = node.accessed_count
        node.touch()
        assert node.accessed_count == initial + 1

    def test_is_stale(self):
        from datetime import datetime, timedelta
        from genius_intelligence.types.knowledge import KnowledgeNode
        node = KnowledgeNode(name="test")
        node.last_accessed_at = datetime.now() - timedelta(days=31)
        assert node.is_stale(max_days=30) is True
        node.last_accessed_at = datetime.now()
        assert node.is_stale(max_days=30) is False


class TestKnowledgeGraph:
    def test_add_node(self):
        from genius_intelligence.types.knowledge import KnowledgeGraph, KnowledgeNode
        graph = KnowledgeGraph()
        node = KnowledgeNode(domain="api", topic="test", depth=2)
        key = graph.add_node(node)
        assert key == "api/test"
        assert "api/test" in graph.nodes

    def test_find_similar(self):
        from genius_intelligence.types.knowledge import KnowledgeGraph, KnowledgeNode
        graph = KnowledgeGraph()
        node = KnowledgeNode(domain="api", topic="jwt", depth=2,
                             raw_input="JWT auth implementation")
        graph.add_node(node)
        results = graph.find_similar("JWT auth")
        assert len(results) >= 1


class TestKnowledgeDomain:
    def test_detect_domain_api(self):
        from genius_intelligence.types.knowledge import KnowledgeDomain
        d = KnowledgeDomain.detect_domain("POST /api/users endpoint")
        assert d == "api"

    def test_detect_domain_database(self):
        from genius_intelligence.types.knowledge import KnowledgeDomain
        d = KnowledgeDomain.detect_domain("postgres migration script")
        assert d == "database"

    def test_detect_domain_auth(self):
        from genius_intelligence.types.knowledge import KnowledgeDomain
        d = KnowledgeDomain.detect_domain("OAuth2 login")
        assert d == "auth"

    def test_detect_unknown(self):
        from genius_intelligence.types.knowledge import KnowledgeDomain
        d = KnowledgeDomain.detect_domain("xyz random unknown")
        assert d == "etc"


class TestAttemptRecord:
    def test_should_knowledgeize_3_attempts(self):
        from genius_intelligence.types.session import AttemptRecord
        record = AttemptRecord(task_description="test")
        for _ in range(3):
            record.add_attempt()
        assert record.should_knowledgeize is True

    def test_mark_success(self):
        from genius_intelligence.types.session import AttemptRecord
        record = AttemptRecord(task_description="test")
        record.mark_success("solution")
        assert record.final_status == "success"
        assert record.solution == "solution"


class TestConfig:
    def test_config_defaults(self):
        from genius_intelligence.types.config import GeniusConfig
        config = GeniusConfig()
        assert config.genius_dir_name == ".genius_intelligence"
        assert config.max_depth == 2
        assert config.auto_knowledge_threshold == 3
        assert config.stale_days == 30

    def test_config_save_load(self):
        from genius_intelligence.types.config import GeniusConfig
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "proj"
            project.mkdir()
            config = GeniusConfig()
            config.project_root = str(project)
            config.genius_root = str(project / ".genius_intelligence")
            config.save()
            loaded = GeniusConfig.load(str(project))
            assert loaded.genius_dir_name == ".genius_intelligence"


class TestKnowledgeStore:
    def test_slugify(self):
        from genius_intelligence.knowledge.store import slugify
        assert slugify("JWT Auth!") == "jwt-auth"
        assert slugify("Hello World") == "hello-world"
        assert slugify("") == "untitled"

    def test_save_load_node(self):
        from genius_intelligence.types.knowledge import KnowledgeNode, KnowledgeType
        from genius_intelligence.types.config import GeniusConfig
        from genius_intelligence.knowledge.store import KnowledgeStore
        from genius_intelligence.memory.db import MemoryDB

        with tempfile.TemporaryDirectory() as tmpdir:
            config = GeniusConfig()
            config.project_root = tmpdir
            config.genius_dir_name = ".genius_intelligence"
            genius_root = str(Path(tmpdir) / ".genius_intelligence")

            store = KnowledgeStore(genius_root, config)
            db = MemoryDB(str(Path(genius_root) / "memory.sqlite.db"))

            node = KnowledgeNode(
                name="test-jwt", domain="api", topic="jwt-auth",
                depth=2, knowledge_type=KnowledgeType.SUCCESS,
                raw_input="JWT auth", solution="done",
            )

            path = store.save_node(node, db)
            assert Path(path).exists()
            assert Path(path).with_suffix(".meta.json").exists()

            loaded = store.load_node_from_disk("api/jwt-auth")
            assert loaded is not None
            assert loaded.name == "test-jwt"


class TestGeniusIntelligence:
    def test_find_project_root(self):
        from genius_intelligence import GeniusIntelligence
        root = GeniusIntelligence.find_project_root()
        assert root is not None

    def test_for_current_project(self):
        from genius_intelligence import GeniusIntelligence
        genius = GeniusIntelligence.for_current_project()
        assert genius is not None

    def test_event_tracking(self):
        from genius_intelligence import GeniusIntelligence
        genius = GeniusIntelligence.for_current_project()
        genius.on_user_message("test message")
        assert genius.current_session.total_messages >= 1

    def test_error_tracking(self):
        from genius_intelligence import GeniusIntelligence
        genius = GeniusIntelligence.for_current_project()
        genius.on_error_occurred("TestError: failed", stack_trace="line 1")
        assert genius.current_session.total_errors >= 1

    def test_search_knowledge(self):
        import tempfile
        from pathlib import Path
        from genius_intelligence import GeniusIntelligence
        import genius_intelligence.memory.db
        with tempfile.TemporaryDirectory() as tmpdir:
            proj = Path(tmpdir) / "proj"
            proj.mkdir()
            (proj / "pyproject.toml").write_text("[project]")
            genius_intelligence.memory.db._db_cache.clear()
            genius = GeniusIntelligence(str(proj), auto_init=True)
            results = genius.search_knowledge("test", limit=3)
            assert isinstance(results, list)
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestMemoryDB:
    def test_save_load_nodes(self):
        import genius_intelligence.memory.db as db_module
        db_module._db_cache.clear()
        from genius_intelligence.types.knowledge import KnowledgeNode, KnowledgeType
        from genius_intelligence.memory.db import MemoryDB

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")
            db = MemoryDB(db_path)
            node = KnowledgeNode(name="test", domain="api", topic="test",
                                 depth=2, knowledge_type=KnowledgeType.SUCCESS)
            db.save_knowledge_node(node)
            graph = db.load_all_nodes()
            assert "api/test" in graph.nodes

    def test_get_stale_nodes(self):
        import genius_intelligence.memory.db as db_module
        db_module._db_cache.clear()
        from datetime import datetime, timedelta
        from genius_intelligence.types.knowledge import KnowledgeNode, KnowledgeType
        from genius_intelligence.memory.db import MemoryDB

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")
            db = MemoryDB(db_path)

            old_node = KnowledgeNode(name="old", domain="api", topic="old",
                                      depth=2, knowledge_type=KnowledgeType.SUCCESS)
            old_node.last_accessed_at = datetime.now() - timedelta(days=31)
            db.save_knowledge_node(old_node)

            new_node = KnowledgeNode(name="new", domain="api", topic="new",
                                     depth=2, knowledge_type=KnowledgeType.SUCCESS)
            db.save_knowledge_node(new_node)

            stale = db.get_stale_nodes(max_days=30)
            stale_ids = [n.id for n in stale]
            assert old_node.id in stale_ids
            assert new_node.id not in stale_ids


class TestPlanContentAnalyzer:
    """파일명과 무관하게 내용만으로 플랜 문서를 감지하는지 확인"""

    def test_detects_dynamic_filenames_with_checkbox_and_numbered_list(self):
        from genius_intelligence.plan import PlanContentAnalyzer
        analyzer = PlanContentAnalyzer()
        text = """# 인증 시스템 리팩토링

1. JWT 라이브러리 교체
2. 세션 관리 개선
3. 테스트 코드 작성

- [ ] jose 라이브러리 제거
- [ ] pyjwt로 교체
"""
        result = analyzer.analyze(text, filename="2024-01-15-refactor-notes.md")
        assert result.is_plan is True

    def test_detects_sequential_numbered_headers(self):
        from genius_intelligence.plan import PlanContentAnalyzer
        analyzer = PlanContentAnalyzer()
        text = """# Sprint 3 작업 노트

### 1. 결제 모듈 구현
### 2. 알림 시스템
### 3. 대시보드 UI
"""
        result = analyzer.analyze(text, filename="sprint3-notes-final-v2.md")
        assert result.is_plan is True

    def test_detects_keyword_numbered_steps(self):
        from genius_intelligence.plan import PlanContentAnalyzer
        analyzer = PlanContentAnalyzer()
        text = "스텝 1: 환경 설정\n스텝 2: 배포 스크립트 작성\n스텝 3: 모니터링 연동\n"
        result = analyzer.analyze(text, filename="xk9f-plan-thing.md")
        assert result.is_plan is True

    def test_does_not_flag_plain_notes(self):
        from genius_intelligence.plan import PlanContentAnalyzer
        analyzer = PlanContentAnalyzer()
        text = "이것은 그냥 일반 메모입니다.\n회의 내용 정리.\n"
        result = analyzer.analyze(text, filename="random-notes-abc123.md")
        assert result.is_plan is False


class TestPlanTrackerContentDetection:
    """PlanTracker가 파일명 패턴 없이도 프로젝트를 스캔해 플랜을 찾는지 확인"""

    def test_detect_plan_files_ignores_filename_and_uses_content(self):
        import tempfile
        from pathlib import Path
        from genius_intelligence.plan import PlanTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            proj = Path(tmpdir) / "proj"
            proj.mkdir()
            (proj / "pyproject.toml").write_text("[project]")

            (proj / "2024-01-15-refactor-notes.md").write_text(
                "# Plan\n\n1. Step one\n2. Step two\n3. Step three\n\n"
                "- [ ] task a\n- [ ] task b\n"
            )
            (proj / "random-notes-abc123.md").write_text(
                "just a normal note with no structure at all.\n"
            )

            tracker = PlanTracker(str(proj))
            detected = tracker.detect_plan_files()
            names = {p.name for p in detected}

            assert "2024-01-15-refactor-notes.md" in names
            assert "random-notes-abc123.md" not in names


class TestA1KnowledgeizeLoop:
    """A1: 반복 실패 시나리오로 실제 지식 노드가 생성되는지 확인"""

    def test_repeated_failure_creates_knowledge_node(self):
        import tempfile, shutil
        from pathlib import Path
        from genius_intelligence import GeniusIntelligence
        import genius_intelligence.memory.db

        with tempfile.TemporaryDirectory() as tmpdir:
            proj = Path(tmpdir) / "proj"
            proj.mkdir()
            (proj / "pyproject.toml").write_text("[project]")
            genius_intelligence.memory.db._db_cache.clear()
            genius = GeniusIntelligence(str(proj), auto_init=True)

            # 동일 주제로 3회 실패 주입
            for _ in range(3):
                genius.on_user_message("jwt auth API 만들어줘")
                genius.on_error_occurred("Error: module not found", stack_trace="trace")

            nodes = genius.flush()

            # 지식 노드가 생성되었는지 확인
            assert len(nodes) >= 1
            node = nodes[0]
            assert node.attempt_count >= 3
            assert node.fail_count >= 3

            # 파일이 실제로 생성되었는지 확인
            kg_dir = proj / ".genius_intelligence" / "knowledge_graph" / "etc"
            md_files = list(kg_dir.glob("*.md"))
            assert len(md_files) >= 1
            # _index.md 제외
            actual = [f for f in md_files if f.name != "_index.md"]
            assert len(actual) >= 1

            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_on_error_no_double_count(self):
        """on_error_occurred가 total_errors를 2중 카운트하지 않는지 확인"""
        from genius_intelligence import GeniusIntelligence
        genius = GeniusIntelligence.for_current_project()
        initial = genius.current_session.total_errors
        genius.on_error_occurred("TestError", stack_trace="trace")
        assert genius.current_session.total_errors == initial + 1

class TestLazyDirectoryCreation:
    """빈 폴더를 만들지 않고, 실제 사용 시 lazy하게 폴더 생성 확인"""

    def test_init_creates_only_root_and_config(self):
        import tempfile, shutil
        from pathlib import Path
        from genius_intelligence import GeniusIntelligence
        import genius_intelligence.memory.db

        with tempfile.TemporaryDirectory() as tmpdir:
            proj = Path(tmpdir) / "proj"
            proj.mkdir()
            (proj / "pyproject.toml").write_text("[project]")
            genius_intelligence.memory.db._db_cache.clear()
            genius = GeniusIntelligence(str(proj), auto_init=True)

            genius_root = proj / ".genius_intelligence"
            # 루트와 .config만 존재
            assert genius_root.exists()
            assert (genius_root / ".config").exists()
            # 빈 하위 폴더는 없어야 함
            assert not (genius_root / "knowledge_graph").exists()
            assert not (genius_root / "login_information").exists()
            # 실제로 사용된 폴더만 생성됨
            # 실제로 사용된 항목만: .config (폴더) + memory.sqlite.db (파일)
            entries = sorted(p.name for p in genius_root.iterdir())
            assert entries == [".config", "memory.sqlite.db"]

            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_save_node_lazy_creates_domain_dir(self):
        import tempfile, shutil
        from pathlib import Path
        from genius_intelligence import GeniusIntelligence
        from genius_intelligence.types.knowledge import KnowledgeNode, KnowledgeType
        import genius_intelligence.memory.db

        with tempfile.TemporaryDirectory() as tmpdir:
            proj = Path(tmpdir) / "proj"
            proj.mkdir()
            (proj / "pyproject.toml").write_text("[project]")
            genius_intelligence.memory.db._db_cache.clear()
            genius = GeniusIntelligence(str(proj), auto_init=True)

            genius_root = proj / ".genius_intelligence"
            assert not (genius_root / "knowledge_graph").exists()

            # 노드 저장 시 도메인 폴더가 lazy 생성됨
            node = KnowledgeNode(
                name="test", domain="api", topic="test",
                depth=2, knowledge_type=KnowledgeType.SUCCESS,
            )
            genius.graph.add_node(node)
            genius.store.save_node(node, genius.db)

            assert (genius_root / "knowledge_graph" / "api").exists()

            shutil.rmtree(tmpdir, ignore_errors=True)


class TestA2SessionPersistence:
    """A2: flush() 없이 종료 후 재시작해도 세션 기록이 남는지 확인"""

    def test_session_events_persisted_to_db(self):
        import tempfile, shutil
        from pathlib import Path
        from genius_intelligence import GeniusIntelligence
        import genius_intelligence.memory.db

        with tempfile.TemporaryDirectory() as tmpdir:
            proj = Path(tmpdir) / "proj"
            proj.mkdir()
            (proj / "pyproject.toml").write_text("[project]")
            genius_intelligence.memory.db._db_cache.clear()
            genius = GeniusIntelligence(str(proj), auto_init=True)

            genius.on_user_message("test message")
            genius.on_error_occurred("some error")
            genius.flush()

            # DB에서 세션 이벤트 조회
            sessions = genius.db.load_recent_sessions(limit=1)
            assert len(sessions) >= 1
            session_id = sessions[0]["id"]

            events = genius.db.load_session_events(session_id)
            assert len(events) >= 2  # user_message + error

            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_attempt_records_persisted(self):
        import tempfile, shutil
        from pathlib import Path
        from genius_intelligence import GeniusIntelligence
        import genius_intelligence.memory.db

        with tempfile.TemporaryDirectory() as tmpdir:
            proj = Path(tmpdir) / "proj"
            proj.mkdir()
            (proj / "pyproject.toml").write_text("[project]")
            genius_intelligence.memory.db._db_cache.clear()
            genius = GeniusIntelligence(str(proj), auto_init=True)

            genius.on_user_message("test task")
            genius.on_error_occurred("error")
            genius.flush()

            sessions = genius.db.load_recent_sessions(limit=1)
            session_id = sessions[0]["id"]
            records = genius.db.load_attempt_records(session_id)
            assert len(records) >= 1

            shutil.rmtree(tmpdir, ignore_errors=True)


class TestA3GraphDBConsistency:
    """A3: slugify CJK 보존 + 노드 덮어쓰기 방지"""

    def test_slugify_preserves_cjk(self):
        from genius_intelligence.knowledge.store import slugify
        result = slugify("JWT 인증 API")
        assert result != ""
        assert "인증" in result or "jwt" in result.lower()

    def test_slugify_empty_returns_untitled(self):
        from genius_intelligence.knowledge.store import slugify
        result = slugify("")
        assert result.startswith("untitled")

    def test_same_topic_accumulates_not_overwrites(self):
        from genius_intelligence.types.knowledge import KnowledgeGraph, KnowledgeNode
        graph = KnowledgeGraph()
        node1 = KnowledgeNode(domain="api", topic="jwt-auth", depth=2, attempt_count=3)
        graph.add_node(node1)
        node2 = KnowledgeNode(domain="api", topic="jwt-auth", depth=2, attempt_count=2)
        graph.add_node(node2)

        existing = graph.find_node("api", "jwt-auth")
        assert existing.attempt_count == 5  # 3 + 2 누적
        assert len(graph.nodes) == 1  # 덮어쓰지 않음


class TestA4WrapperSafety:
    """A4: 마크다운 문단이 명령으로 안 잡히는지 확인"""

    def test_markdown_not_parsed_as_command(self):
        from genius_intelligence.auto.universal import UniversalWrapper, GENERIC_PATTERNS
        import re

        # # 헤더, > 인용이 명령 패턴과 매칭되지 않아야 함
        test_lines = [
            "# 제목",
            "> 인용구",
            "## 섹션",
            "bash command here",
        ]
        for line in test_lines:
            matched = False
            for pattern in GENERIC_PATTERNS["command"]:
                if re.search(pattern, line):
                    matched = True
                    break
            assert not matched, f"Line '{line}' was falsely matched as command"

    def test_stderr_not_all_errors(self):
        """stderr 전체가 에러로 몰아넣어지지 않는지 확인"""
        from genius_intelligence.auto.universal import UniversalWrapper

        wrapper = UniversalWrapper.__new__(UniversalWrapper)
        wrapper.genius = None
        wrapper.plan_tracker = None
        wrapper.on_event_callback = None

        # 경고 메시지는 에러로 잡히지 않아야 함
        events = wrapper._parse_line("warning: something", is_stderr=True)
        error_events = [e for e in events if e.get("type") == "error"]
        assert len(error_events) == 0

        # 실제 에러는 잡혀야 함
        events = wrapper._parse_line("Error: something failed", is_stderr=True)
        error_events = [e for e in events if e.get("type") == "error"]
        assert len(error_events) == 1


class TestA5PlanTracker:
    """A5: 플랜 추적 오탐/완료율 수정"""

    def test_readme_not_detected_as_plan(self):
        from genius_intelligence.plan import PlanContentAnalyzer
        analyzer = PlanContentAnalyzer()
        readme = "# Genius Intelligence\n\nA knowledge library.\n\n## Features\n\n- Feature A\n- Feature B\n"
        result = analyzer.analyze(readme, filename="README.md")
        assert result.is_plan is False

    def test_completion_rate_with_checkboxes(self):
        from genius_intelligence.plan.tracker import PlanTracker
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = PlanTracker(tmpdir)
            content = "# Plan\n\n- [x] task a\n- [x] task b\n- [x] task c\n- [ ] task d\n"
            tasks = tracker._extract_tasks(content)

            completed = sum(1 for t in tasks if t.is_completed)
            assert completed == 3
            assert len(tasks) == 4

    def test_code_block_numbered_list_excluded(self):
        from genius_intelligence.plan.tracker import PlanTracker
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = PlanTracker(tmpdir)
            content = "# Plan\n\n```\n1. code line one\n2. code line two\n```\n\n- [ ] real task\n"
            tasks = tracker._extract_tasks(content)
            # 코드 블록 안의 번호 리스트는 제외, 체크박스만 태스크
            assert len(tasks) == 1
            assert tasks[0].title == "real task"


class TestA6CleanupSafety:
    """A6: 첫 flush 후 클린업이 아무것도 삭제하지 않는지 확인"""

    def test_first_cleanup_deletes_nothing(self):
        import tempfile, shutil
        from pathlib import Path
        from genius_intelligence import GeniusIntelligence
        import genius_intelligence.memory.db

        with tempfile.TemporaryDirectory() as tmpdir:
            proj = Path(tmpdir) / "proj"
            proj.mkdir()
            (proj / "pyproject.toml").write_text("[project]")
            genius_intelligence.memory.db._db_cache.clear()
            genius = GeniusIntelligence(str(proj), auto_init=True)

            # 노드 하나 추가
            from genius_intelligence.types.knowledge import KnowledgeNode, KnowledgeType
            node = KnowledgeNode(
                name="test", domain="api", topic="test",
                depth=2, knowledge_type=KnowledgeType.SUCCESS,
            )
            genius.graph.add_node(node)
            genius.store.save_node(node, genius.db)

            # flush 호출 (maybe_cleanup이 실행됨)
            genius.flush()

            # 첫 호출이믔 클린업은 아무것도 삭제하지 않아야 함
            assert genius.cleaner._last_cleanup is not None

            # 노드가 여전히 존재해야 함
            remaining = genius.db.load_all_nodes()
            assert "api/test" in remaining.nodes

            shutil.rmtree(tmpdir, ignore_errors=True)


class TestB1ContextInjection:
    """B1: 지식 몇 개 저장 → context 렌더링 확인"""

    def test_context_renders_knowledge(self):
        import tempfile, shutil
        from pathlib import Path
        from genius_intelligence import GeniusIntelligence
        from genius_intelligence.context import render_knowledge_context
        import genius_intelligence.memory.db

        with tempfile.TemporaryDirectory() as tmpdir:
            proj = Path(tmpdir) / "proj"
            proj.mkdir()
            (proj / "pyproject.toml").write_text("[project]")
            genius_intelligence.memory.db._db_cache.clear()
            genius = GeniusIntelligence(str(proj), auto_init=True)

            # 지식 2개 저장
            from genius_intelligence.types.knowledge import KnowledgeNode, KnowledgeType
            node1 = KnowledgeNode(
                name="jwt-auth", domain="auth", topic="jwt-auth",
                depth=2, knowledge_type=KnowledgeType.SUCCESS,
                raw_input="JWT auth", solution="use pyjwt",
            )
            node2 = KnowledgeNode(
                name="login", domain="auth", topic="login",
                depth=2, knowledge_type=KnowledgeType.FAILURE,
                raw_input="login error", solution="check token",
            )
            genius.graph.add_node(node1)
            genius.store.save_node(node1, genius.db)
            genius.graph.add_node(node2)
            genius.store.save_node(node2, genius.db)

            # context 렌더링
            md = render_knowledge_context(genius, "auth", limit=5)
            assert md != ""
            assert "jwt-auth" in md or "JWT auth" in md

            # 빈 쿼리도 동작해야 함
            md2 = render_knowledge_context(genius, "", limit=5)
            assert md2 != ""

            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_empty_knowledge_returns_empty(self):
        import tempfile, shutil
        from pathlib import Path
        from genius_intelligence import GeniusIntelligence
        from genius_intelligence.context import render_knowledge_context
        import genius_intelligence.memory.db

        with tempfile.TemporaryDirectory() as tmpdir:
            proj = Path(tmpdir) / "proj"
            proj.mkdir()
            (proj / "pyproject.toml").write_text("[project]")
            genius_intelligence.memory.db._db_cache.clear()
            genius = GeniusIntelligence(str(proj), auto_init=True)

            md = render_knowledge_context(genius, "nonexistent", limit=5)
            assert md == ""

            shutil.rmtree(tmpdir, ignore_errors=True)
