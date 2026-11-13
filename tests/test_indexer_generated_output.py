"""Machine-generated run output stays out of the index; the documents beside it do not."""
from pathlib import Path

import pytest

from rat.crawler.indexer import Indexer


@pytest.fixture
def indexer():
    return Indexer.__new__(Indexer)  # is_ignored/discover_files need no database


@pytest.mark.parametrize("path", [
    "/u/Github/vrptw/results/run/shard_1/session/incumbent_000016.json",
    "/u/Github/proj/Outputs/eval.log",
    "/u/Github/proj/wandb/run-1/files/config.yaml",
])
def test_generated_output_is_ignored(indexer, path):
    assert indexer.is_ignored(Path(path))


@pytest.mark.parametrize("path", [
    "/u/Github/tdtu-computer-organization/ly-thuyet-giua-ky-502044.pdf",
    "/u/Documents/result_summary.docx",  # a file name, not a results/ folder
])
def test_documents_are_kept(indexer, path):
    assert not indexer.is_ignored(Path(path))


def test_discovery_does_not_descend_into_results(indexer, tmp_path):
    (tmp_path / "results" / "run").mkdir(parents=True)
    (tmp_path / "results" / "run" / "incumbent.json").write_text("{}")
    (tmp_path / "notes.md").write_text("# notes")
    indexer._cancel_flag = False
    assert indexer.discover_files([str(tmp_path)]) == [str(tmp_path / "notes.md")]
