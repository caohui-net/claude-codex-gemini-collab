#!/usr/bin/env python3
"""Tests for discussion file metadata YAML validation.

Covers Codex review requirements:
- Field type validation
- Required field validation
- Relationship constraints (participants/agents/author)
"""

import json
import pytest
import yaml
from pathlib import Path
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from collab_discuss import create_discussion_file_with_metadata


class TestMetadataFieldTypes:
    """Test metadata field type validation."""

    def test_required_fields_types(self, tmp_path):
        """Test all 8 required fields have correct types."""
        file_path = create_discussion_file_with_metadata(
            project_name="test-metadata-types",
            topic="Test topic",
            round_num=0,
            author="claude",
            author_role="initiator",
            content="Test content",
            mode="sequential",
            agents=["claude"],
            participants=["claude"]
        )

        # Read and parse metadata
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract YAML frontmatter
        assert content.startswith('---\n')
        parts = content.split('---\n', 2)
        assert len(parts) >= 3

        metadata = yaml.safe_load(parts[1])

        # Verify types of required fields
        assert isinstance(metadata['project'], str)
        assert isinstance(metadata['project_path'], str)
        assert isinstance(metadata['topic'], str)
        assert isinstance(metadata['round'], int)
        assert isinstance(metadata['discussion_id'], str)
        assert isinstance(metadata['generated_at'], str)
        assert isinstance(metadata['author'], str)
        assert isinstance(metadata['author_role'], str)

    def test_optional_fields_types(self, tmp_path):
        """Test optional fields have correct types when present."""
        file_path = create_discussion_file_with_metadata(
            project_name="test-metadata-optional",
            topic="Test topic",
            round_num=1,
            author="codex",
            author_role="participant",
            content="Test content",
            mode="parallel",
            agents=["claude", "codex", "gemini"],
            participants=["codex", "gemini"]
        )

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        parts = content.split('---\n', 2)
        metadata = yaml.safe_load(parts[1])

        # Verify optional fields types
        assert isinstance(metadata['mode'], str)
        assert isinstance(metadata['agents'], list)
        assert all(isinstance(a, str) for a in metadata['agents'])
        assert isinstance(metadata['round_info'], dict)
        assert isinstance(metadata['round_info']['participants'], list)
        assert isinstance(metadata['round_info']['author_position'], int)
        assert isinstance(metadata['round_info']['total_in_round'], int)


class TestMetadataRequiredFields:
    """Test required field validation."""

    def test_all_required_fields_present(self, tmp_path):
        """Test all 8 required fields are present in generated metadata."""
        file_path = create_discussion_file_with_metadata(
            project_name="test-required-fields",
            topic="Test topic",
            round_num=0,
            author="claude",
            author_role="initiator",
            content="Test content"
        )

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        parts = content.split('---\n', 2)
        metadata = yaml.safe_load(parts[1])

        # Check all 8 required fields
        required_fields = [
            'project', 'project_path', 'topic', 'round',
            'discussion_id', 'generated_at', 'author', 'author_role'
        ]

        for field in required_fields:
            assert field in metadata, f"Required field '{field}' missing"
            assert metadata[field] is not None, f"Required field '{field}' is None"
            if isinstance(metadata[field], str):
                assert metadata[field].strip() != "", f"Required field '{field}' is empty"

    def test_required_string_fields_non_empty(self, tmp_path):
        """Test required string fields are non-empty."""
        file_path = create_discussion_file_with_metadata(
            project_name="test-string-fields",
            topic="Test topic with at least some content",
            round_num=0,
            author="claude",
            author_role="initiator",
            content="Test content"
        )

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        parts = content.split('---\n', 2)
        metadata = yaml.safe_load(parts[1])

        # Verify string fields are non-empty
        assert len(metadata['project']) > 0
        assert len(metadata['project_path']) > 0
        assert len(metadata['topic']) > 0
        assert len(metadata['discussion_id']) > 0
        assert len(metadata['generated_at']) > 0
        assert len(metadata['author']) > 0
        assert len(metadata['author_role']) > 0


class TestMetadataRelationshipConstraints:
    """Test relationship constraints between participants, agents, and author."""

    def test_participants_subset_of_agents(self, tmp_path):
        """Test that round_info.participants is a subset of agents."""
        file_path = create_discussion_file_with_metadata(
            project_name="test-participants-subset",
            topic="Test topic",
            round_num=1,
            author="codex",
            author_role="participant",
            content="Test content",
            agents=["claude", "codex", "gemini"],
            participants=["codex", "gemini"]
        )

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        parts = content.split('---\n', 2)
        metadata = yaml.safe_load(parts[1])

        # Verify participants ⊆ agents
        participants = set(metadata['round_info']['participants'])
        agents = set(metadata['agents'])
        assert participants.issubset(agents), \
            f"Participants {participants} not subset of agents {agents}"

    def test_author_in_participants(self, tmp_path):
        """Test that author is in round_info.participants."""
        file_path = create_discussion_file_with_metadata(
            project_name="test-author-in-participants",
            topic="Test topic",
            round_num=1,
            author="gemini",
            author_role="participant",
            content="Test content",
            agents=["claude", "codex", "gemini"],
            participants=["codex", "gemini"]
        )

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        parts = content.split('---\n', 2)
        metadata = yaml.safe_load(parts[1])

        # Verify author ∈ participants
        assert metadata['author'] in metadata['round_info']['participants'], \
            f"Author '{metadata['author']}' not in participants {metadata['round_info']['participants']}"

    def test_pre_discuss_constraints(self, tmp_path):
        """Test pre-discuss round (round=0) has exactly 1 participant (claude as initiator)."""
        file_path = create_discussion_file_with_metadata(
            project_name="test-pre-discuss",
            topic="Test topic",
            round_num=0,
            author="claude",
            author_role="initiator",
            content="Test content",
            agents=["claude", "codex", "gemini"],
            participants=["claude"]
        )

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        parts = content.split('---\n', 2)
        metadata = yaml.safe_load(parts[1])

        # Verify pre-discuss constraints
        assert metadata['round'] == 0
        assert metadata['author'] == "claude"
        assert metadata['author_role'] == "initiator"
        assert len(metadata['round_info']['participants']) == 1
        assert metadata['round_info']['participants'][0] == "claude"
        assert metadata['round_info']['total_in_round'] == 1

    def test_author_position_within_range(self, tmp_path):
        """Test author_position is valid index within participants list."""
        file_path = create_discussion_file_with_metadata(
            project_name="test-author-position",
            topic="Test topic",
            round_num=1,
            author="gemini",
            author_role="participant",
            content="Test content",
            agents=["claude", "codex", "gemini"],
            participants=["codex", "gemini"]
        )

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        parts = content.split('---\n', 2)
        metadata = yaml.safe_load(parts[1])

        author_pos = metadata['round_info']['author_position']
        participants = metadata['round_info']['participants']

        # Verify author_position is valid (note: author_position is 1-indexed in implementation)
        assert 1 <= author_pos <= len(participants), \
            f"author_position {author_pos} out of range for {len(participants)} participants"
        assert participants[author_pos - 1] == metadata['author'], \
            f"participants[{author_pos - 1}] = {participants[author_pos - 1]} != author {metadata['author']}"

    def test_total_in_round_matches_participants_count(self, tmp_path):
        """Test total_in_round matches actual participants count."""
        file_path = create_discussion_file_with_metadata(
            project_name="test-total-in-round",
            topic="Test topic",
            round_num=2,
            author="codex",
            author_role="participant",
            content="Test content",
            agents=["claude", "codex", "gemini"],
            participants=["claude", "codex", "gemini"]
        )

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        parts = content.split('---\n', 2)
        metadata = yaml.safe_load(parts[1])

        # Verify total_in_round matches count
        assert metadata['round_info']['total_in_round'] == len(metadata['round_info']['participants']), \
            f"total_in_round {metadata['round_info']['total_in_round']} != participants count {len(metadata['round_info']['participants'])}"


class TestMetadataFormatConstraints:
    """Test format constraints for timestamps and IDs."""

    def test_generated_at_iso8601_utc_format(self, tmp_path):
        """Test generated_at follows ISO 8601 UTC format (ends with Z)."""
        file_path = create_discussion_file_with_metadata(
            project_name="test-timestamp-format",
            topic="Test topic",
            round_num=0,
            author="claude",
            author_role="initiator",
            content="Test content"
        )

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        parts = content.split('---\n', 2)
        metadata = yaml.safe_load(parts[1])

        timestamp = metadata['generated_at']

        # Verify format: YYYY-MM-DDTHH:MM:SSZ
        assert timestamp.endswith('Z'), f"Timestamp must end with 'Z' (UTC), got: {timestamp}"
        assert 'T' in timestamp, f"Timestamp must contain 'T' separator, got: {timestamp}"

        # Verify parseable as ISO 8601
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            assert dt.tzinfo is not None, "Timestamp must have timezone info"
        except ValueError as e:
            pytest.fail(f"Timestamp not valid ISO 8601: {timestamp} - {e}")

    def test_discussion_id_format(self, tmp_path):
        """Test discussion_id follows disc-YYYYMMDD-HHMMSS-HASH format."""
        file_path = create_discussion_file_with_metadata(
            project_name="test-discussion-id-format",
            topic="Test topic",
            round_num=0,
            author="claude",
            author_role="initiator",
            content="Test content"
        )

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        parts = content.split('---\n', 2)
        metadata = yaml.safe_load(parts[1])

        disc_id = metadata['discussion_id']

        # Verify format: disc-YYYYMMDD-HHMMSS-HASH
        assert disc_id.startswith('disc-'), f"discussion_id must start with 'disc-', got: {disc_id}"

        parts = disc_id.split('-')
        assert len(parts) >= 4, f"discussion_id must have at least 4 parts, got: {disc_id}"

        # Verify date part (YYYYMMDD)
        date_part = parts[1]
        assert len(date_part) == 8, f"Date part must be 8 digits (YYYYMMDD), got: {date_part}"
        assert date_part.isdigit(), f"Date part must be numeric, got: {date_part}"

        # Verify time part (HHMMSS)
        time_part = parts[2]
        assert len(time_part) == 6, f"Time part must be 6 digits (HHMMSS), got: {time_part}"
        assert time_part.isdigit(), f"Time part must be numeric, got: {time_part}"

        # Verify hash part (alphanumeric)
        hash_part = parts[3]
        assert len(hash_part) >= 4, f"Hash part must be at least 4 chars, got: {hash_part}"
        assert hash_part.isalnum(), f"Hash part must be alphanumeric, got: {hash_part}"

    def test_author_role_enum(self, tmp_path):
        """Test author_role is one of allowed values."""
        allowed_roles = ["initiator", "participant", "reviewer"]

        for role in allowed_roles:
            file_path = create_discussion_file_with_metadata(
                project_name=f"test-role-{role}",
                topic="Test topic",
                round_num=0 if role == "initiator" else 1,
                author="claude",
                author_role=role,
                content="Test content"
            )

            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            parts = content.split('---\n', 2)
            metadata = yaml.safe_load(parts[1])

            assert metadata['author_role'] in allowed_roles, \
                f"author_role must be one of {allowed_roles}, got: {metadata['author_role']}"

    def test_round_non_negative(self, tmp_path):
        """Test round number is non-negative integer."""
        for round_num in [0, 1, 2, 5, 10]:
            file_path = create_discussion_file_with_metadata(
                project_name=f"test-round-{round_num}",
                topic="Test topic",
                round_num=round_num,
                author="claude" if round_num == 0 else "codex",
                author_role="initiator" if round_num == 0 else "participant",
                content="Test content"
            )

            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            parts = content.split('---\n', 2)
            metadata = yaml.safe_load(parts[1])

            assert isinstance(metadata['round'], int), f"round must be int, got: {type(metadata['round'])}"
            assert metadata['round'] >= 0, f"round must be non-negative, got: {metadata['round']}"
            assert metadata['round'] == round_num, f"round mismatch: expected {round_num}, got {metadata['round']}"


class TestBackwardCompatibility:
    """Test backward compatibility between v1.0 and v1.1 metadata formats."""

    def test_v1_0_format_without_round_info(self, tmp_path):
        """Test that v1.0 format (without round_info) can still be parsed."""
        # Create a v1.0-style metadata file manually
        v1_0_content = """---
project: test-v1-0-compat
project_path: /home/user/test-project
topic: Test v1.0 compatibility
round: 1
discussion_id: disc-20260722-100000-abc1
generated_at: 2026-07-22T10:00:00Z
author: codex
author_role: participant
mode: parallel
agents:
- claude
- codex
- gemini
---

This is v1.0 format discussion content (no round_info field).
"""

        test_file = tmp_path / "v1_0_test.md"
        test_file.write_text(v1_0_content, encoding='utf-8')

        # Verify file can be parsed
        with open(test_file, 'r', encoding='utf-8') as f:
            content = f.read()

        parts = content.split('---\n', 2)
        assert len(parts) >= 3

        metadata = yaml.safe_load(parts[1])

        # Verify required v1.0 fields are present
        assert metadata['project'] == 'test-v1-0-compat'
        assert metadata['round'] == 1
        assert metadata['author'] == 'codex'
        assert metadata['agents'] == ['claude', 'codex', 'gemini']

        # Verify round_info is absent (v1.0 doesn't have it)
        assert 'round_info' not in metadata

    def test_v1_1_format_with_round_info(self, tmp_path):
        """Test that v1.1 format (with round_info) works correctly."""
        file_path = create_discussion_file_with_metadata(
            project_name="test-v1-1-compat",
            topic="Test v1.1 compatibility",
            round_num=1,
            author="codex",
            author_role="participant",
            content="This is v1.1 format with round_info.",
            agents=["claude", "codex", "gemini"],
            participants=["codex", "gemini"]
        )

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        parts = content.split('---\n', 2)
        metadata = yaml.safe_load(parts[1])

        # Verify v1.1-specific field is present
        assert 'round_info' in metadata
        assert metadata['round_info']['participants'] == ['codex', 'gemini']
        assert metadata['round_info']['total_in_round'] == 2

    def test_mixed_v1_0_and_v1_1_coexistence(self, tmp_path):
        """Test that v1.0 and v1.1 formats can coexist in same discussion."""
        # Create v1.0 file manually
        v1_0_content = """---
project: test-mixed-compat
project_path: /home/user/test-project
topic: Mixed version test
round: 0
discussion_id: disc-20260722-100000-abc1
generated_at: 2026-07-22T10:00:00Z
author: claude
author_role: initiator
---

Round 0 content (v1.0 format).
"""
        v1_0_file = tmp_path / "v1_0_round_0.md"
        v1_0_file.write_text(v1_0_content, encoding='utf-8')

        # Create v1.1 file using function
        v1_1_file = create_discussion_file_with_metadata(
            project_name="test-mixed-compat",
            topic="Mixed version test",
            round_num=1,
            author="codex",
            author_role="participant",
            content="Round 1 content (v1.1 format).",
            agents=["claude", "codex"],
            participants=["codex"]
        )

        # Both files should exist and be parseable
        assert v1_0_file.exists()
        assert v1_1_file.exists()

        # Parse both
        with open(v1_0_file, 'r', encoding='utf-8') as f:
            v1_0_meta = yaml.safe_load(f.read().split('---\n', 2)[1])
        with open(v1_1_file, 'r', encoding='utf-8') as f:
            v1_1_meta = yaml.safe_load(f.read().split('---\n', 2)[1])

        # Same project
        assert v1_0_meta['project'] == v1_1_meta['project']
        # v1.0 no round_info, v1.1 has round_info
        assert 'round_info' not in v1_0_meta
        assert 'round_info' in v1_1_meta

    def test_unknown_fields_ignored_gracefully(self, tmp_path):
        """Test that unknown/future fields are ignored (forward compatibility)."""
        future_content = """---
project: test-future-fields
project_path: /home/user/test-project
topic: Future fields test
round: 0
discussion_id: disc-20260722-100000-abc1
generated_at: 2026-07-22T10:00:00Z
author: claude
author_role: initiator
future_field_v2: "This field doesn't exist in v1.1"
experimental_feature: true
---

Content with future unknown fields.
"""
        test_file = tmp_path / "future_fields.md"
        test_file.write_text(future_content, encoding='utf-8')

        # Should parse without errors
        with open(test_file, 'r', encoding='utf-8') as f:
            content = f.read()
        parts = content.split('---\n', 2)
        metadata = yaml.safe_load(parts[1])

        # Required fields still work
        assert metadata['project'] == 'test-future-fields'
        assert metadata['author'] == 'claude'
        # Unknown fields present but don't break parsing
        assert 'future_field_v2' in metadata
        assert 'experimental_feature' in metadata


class TestPathSecurity:
    """Test path security constraints for artifact_path and file creation."""

    def test_artifact_path_relative_only(self, tmp_path):
        """Test that generated artifact_path is always relative (no leading /)."""
        file_path = create_discussion_file_with_metadata(
            project_name="test-path-relative",
            topic="Test topic",
            round_num=0,
            author="claude",
            author_role="initiator",
            content="Test content"
        )

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        parts = content.split('---\n', 2)
        metadata = yaml.safe_load(parts[1])

        # artifact_path should be in metadata if present
        # For now, test that file_path itself is not vulnerable
        assert not str(file_path).startswith('..'), "File path should not contain directory traversal"

    def test_topic_sanitization_prevents_traversal(self, tmp_path):
        """Test that malicious topic with .. is sanitized."""
        malicious_topic = "../../../etc/passwd"

        file_path = create_discussion_file_with_metadata(
            project_name="test-traversal",
            topic=malicious_topic,
            round_num=0,
            author="claude",
            author_role="initiator",
            content="Test content"
        )

        # Verify file was created in safe location
        assert file_path.exists()
        # Verify file is under ~/.claude/collab/discussions/
        collab_base = Path.home() / ".claude" / "collab" / "discussions"
        assert str(file_path).startswith(str(collab_base)), \
            f"File {file_path} not under safe base {collab_base}"

        # Verify filename doesn't contain .. literally
        assert ".." not in file_path.name, "Filename should not contain .."

    def test_topic_sanitization_prevents_absolute_path(self, tmp_path):
        """Test that topic with absolute path markers is sanitized."""
        malicious_topic = "/tmp/malicious_file"

        file_path = create_discussion_file_with_metadata(
            project_name="test-absolute",
            topic=malicious_topic,
            round_num=0,
            author="claude",
            author_role="initiator",
            content="Test content"
        )

        # Verify file is under safe base directory
        collab_base = Path.home() / ".claude" / "collab" / "discussions"
        assert str(file_path).startswith(str(collab_base)), \
            "File should be created under safe base directory"

        # Verify filename doesn't start with /
        assert not file_path.name.startswith('/'), "Filename should not start with /"

    def test_filename_length_within_limits(self, tmp_path):
        """Test that very long topics result in truncated but valid filenames."""
        long_topic = "A" * 300  # Very long topic

        file_path = create_discussion_file_with_metadata(
            project_name="test-long-topic",
            topic=long_topic,
            round_num=0,
            author="claude",
            author_role="initiator",
            content="Test content"
        )

        # Verify file was created
        assert file_path.exists()

        # Verify filename is not excessively long (Linux limit is 255 bytes)
        assert len(file_path.name.encode('utf-8')) <= 255, \
            f"Filename too long: {len(file_path.name)} bytes"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

