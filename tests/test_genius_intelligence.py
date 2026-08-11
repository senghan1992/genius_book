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
            genius = GeniusIntelligence.for_current_project(str(proj))
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
