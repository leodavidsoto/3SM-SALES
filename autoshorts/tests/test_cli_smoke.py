"""Smoke tests for autoshorts CLI — no external services needed."""

import json
import hashlib
import tempfile
from pathlib import Path

import pytest


@pytest.fixture()
def tmp_env(tmp_path, monkeypatch):
    """Patch all folder paths to a temp directory."""
    import autoshorts.cli as cli

    monkeypatch.setattr(cli, "INPUT_FOLDER", tmp_path / "input")
    monkeypatch.setattr(cli, "OUTPUT_FOLDER", tmp_path / "output")
    monkeypatch.setattr(cli, "STATE_FILE", tmp_path / "state" / "processed.json")
    monkeypatch.setattr(cli, "LEARNINGS_DIR", tmp_path / "learnings")
    monkeypatch.setattr(cli, "HOT_MD", tmp_path / "learnings" / "HOT.md")
    monkeypatch.setattr(cli, "POST_HISTORY", tmp_path / "learnings" / "post-history.jsonl")
    return tmp_path


def test_parser_builds():
    from autoshorts.cli import build_parser

    p = build_parser()
    assert p is not None


def test_parser_all_commands():
    from autoshorts.cli import build_parser

    p = build_parser()
    commands = [
        ["pick"],
        ["transcribe", "video.mp4"],
        ["analyze", "video.mp4"],
        ["extract", "video.mp4"],
        ["hook", "video.mp4"],
        ["preview", "video.mp4"],
        ["publish", "video.mp4", "clip_01"],
        ["mark-processed", "video.mp4"],
        ["learn"],
        ["reflect", "video.mp4"],
    ]
    for argv in commands:
        args = p.parse_args(argv)
        assert args.command == argv[0]


def test_pick_empty_folder(tmp_env, capsys):
    from autoshorts.cli import build_parser, cmd_pick

    args = build_parser().parse_args(["pick"])
    cmd_pick(args)
    out = capsys.readouterr().out
    assert "No video files" in out or "Drop" in out


def test_pick_finds_video(tmp_env, capsys):
    from autoshorts.cli import build_parser, cmd_pick, INPUT_FOLDER

    INPUT_FOLDER.mkdir(parents=True, exist_ok=True)
    fake_video = INPUT_FOLDER / "test_clip.mp4"
    fake_video.write_bytes(b"\x00" * 1024)

    args = build_parser().parse_args(["pick"])
    cmd_pick(args)
    out = capsys.readouterr().out
    assert "PICKED" in out
    assert "test_clip" in out


def test_pick_skips_processed(tmp_env, capsys):
    from autoshorts.cli import build_parser, cmd_pick, INPUT_FOLDER, STATE_FILE

    INPUT_FOLDER.mkdir(parents=True, exist_ok=True)
    fake_video = INPUT_FOLDER / "done.mp4"
    fake_video.write_bytes(b"\xFF" * 512)

    sha = hashlib.sha256(b"\xFF" * 512).hexdigest()
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({sha: "done"}))

    args = build_parser().parse_args(["pick"])
    cmd_pick(args)
    out = capsys.readouterr().out
    assert "PICKED" not in out


def test_slug_from_path():
    from autoshorts.cli import slug_from_path

    assert slug_from_path(Path("my video file.mp4")) == "my_video_file"
    assert slug_from_path(Path("my-video.mp4")) == "my-video"
    assert slug_from_path(Path("..mp4")) == "mp4" or slug_from_path(Path("..mp4")) != ""


def test_sha256_file(tmp_path):
    from autoshorts.cli import sha256_file

    f = tmp_path / "data.bin"
    f.write_bytes(b"hello world")
    digest = sha256_file(f)
    assert len(digest) == 64
    assert digest == hashlib.sha256(b"hello world").hexdigest()


def test_mark_processed(tmp_env):
    from autoshorts.cli import build_parser, cmd_mark_processed, STATE_FILE

    video = tmp_env / "clip.mp4"
    video.write_bytes(b"fake_video_data")

    args = build_parser().parse_args(["mark-processed", str(video)])
    cmd_mark_processed(args)

    assert STATE_FILE.exists()
    data = json.loads(STATE_FILE.read_text())
    assert len(data) == 1
    slug = list(data.values())[0]
    assert slug == "clip"


@pytest.mark.smoke
def test_hot_md_content_missing(tmp_env):
    from autoshorts.cli import hot_md_content

    assert hot_md_content() == ""


@pytest.mark.smoke
def test_hot_md_content_present(tmp_env):
    from autoshorts.cli import hot_md_content, LEARNINGS_DIR, HOT_MD

    LEARNINGS_DIR.mkdir(parents=True, exist_ok=True)
    HOT_MD.write_text("## WHAT WORKS\n- hooks with numbers")
    assert "hooks with numbers" in hot_md_content()
