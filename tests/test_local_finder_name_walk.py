"""The slow filename walk runs only when Spotlight finds nothing and no meaning index exists."""

import threading

from rat.engine import local_finder
from rat.engine.local_finder import HybridFinder


class _Scopes:
    def __init__(self, tmp_path):
        self.lock = threading.Lock()
        self.roots = [tmp_path]
        self.version = 1

    def verify(self, raw, identity=None):  # pragma: no cover - no hit reaches verification
        raise AssertionError("no hit expected")


class _Index:
    def __init__(self, indexed):
        self.indexed = indexed

    def count(self):
        return self.indexed

    def search(self, query, should_cancel):
        return []

    def invalidate_paths(self, paths):  # pragma: no cover
        pass


def _run(monkeypatch, tmp_path, semantic):
    walks = []
    monkeypatch.setattr(local_finder, "spotlight_scopes", lambda *a, **k: ([], [], 1))

    def fake_walk(*args, **kwargs):
        walks.append(args)
        return [], False

    monkeypatch.setattr(local_finder, "name_walk_paths", fake_walk)
    result = HybridFinder(_Scopes(tmp_path), semantic=semantic).search("bai tap giai tich")
    return walks, result


def test_name_walk_is_skipped_when_the_meaning_index_has_content(monkeypatch, tmp_path):
    walks, result = _run(monkeypatch, tmp_path, _Index(indexed=5))
    assert walks == []
    assert result["diagnostics"]["name_walk"] == "not_needed"
    assert result["coverage"]["semantic"] == "queried"


def test_name_walk_runs_when_the_meaning_index_is_empty(monkeypatch, tmp_path):
    walks, result = _run(monkeypatch, tmp_path, _Index(indexed=0))
    assert len(walks) == 1
    assert result["diagnostics"]["name_walk"] == "complete"


def test_name_walk_runs_without_a_meaning_index(monkeypatch, tmp_path):
    walks, result = _run(monkeypatch, tmp_path, None)
    assert len(walks) == 1
    assert result["coverage"]["semantic"] == "disabled"
