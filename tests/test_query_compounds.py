import unicodedata

import pytest

from rat.engine.context_parser import ContextParser
from rat.engine.reranker import Reranker


@pytest.mark.parametrize("query", ["slides giải tích", "slides giai tich", "slides GIẢI TÍCH", "slides giải\t  tích", unicodedata.normalize("NFD", "slides giải tích")])
def test_compound_does_not_leak_component_keywords(query):
    kws = ContextParser.parse_query(query).keywords
    assert kws[:2] == ["giai tich", "slides"]
    assert "giải" not in kws and "tích" not in kws


def test_compound_matching_uses_whole_words_and_preserves_other_occurrences():
    assert "giai tich" not in ContextParser.parse_query("nongiai tich").keywords
    assert ContextParser.parse_query("slides giải tích giải").keywords[:3] == ["giai tich", "slides", "giải"]


def test_longest_compound_wins_without_duplicate_subphrases():
    assert ContextParser.parse_query("bài tập lớn calculus").keywords[:2] == ["bai tap lon", "calculus"]


def test_exact_filename_is_preserved():
    assert ContextParser.parse_query("MA1521Chap1.pdf").keywords == ["MA1521Chap1.pdf"]


def test_unrelated_compound_components_do_not_gain_topic_points():
    context = ContextParser.parse_query("slides giải tích")
    document = dict(file_name="Trinh Bay Slides VRPTW.pptx", file_ext=".pptx", file_size=1, modified_at=1,
                    content_text="giải bài toán; tích hợp bộ tối ưu", matched_facets=["lexical"])
    score, _ = Reranker().compute_heuristic_score(document, context)
    assert score == 60
    assert document["_feats"]["kw_content"] == 0


def test_semantic_only_candidate_can_still_have_filename_points():
    context = ContextParser.parse_query("slides giải tích")
    document = dict(file_name="slides_ch2.pdf", file_ext=".pdf", modified_at=1,
                    content_text="English calculus lecture", matched_facets=["semantic"])
    Reranker().compute_heuristic_score(document, context)
    assert document["_feats"]["kw_word"] == 55


def _deck(name, content, **extra):
    return dict(file_name=name, file_path="/tmp/rat-test/" + name, file_ext=".pptx", file_size=1, modified_at=1,
                content_text=content, matched_facets=["lexical"], **extra)


def _ranked(query, decks):
    results = Reranker().rerank(query, ContextParser.parse_query(query), decks, top_k=10)
    return [item.file_name if hasattr(item, "file_name") else item["file_name"] for item in results]


def test_unrelated_decks_get_no_study_bonuses_and_rank_below_the_real_one():
    """'slides' is a document-type word; matching it must not earn the course-material bonuses."""
    context = ContextParser.parse_query("slides giải tích")
    unrelated = [_deck("Trinh Bay Slides VRPTW.pptx", "giải bài toán; tích hợp bộ tối ưu"),
                 _deck("Marketing Slides Q3.pptx", "chiến lược thương hiệu và quảng cáo")]
    real = _deck("Giai tich 1 - Chuong 2 slides.pptx", "giải tích hàm một biến; đạo hàm và tích phân")
    scorer = Reranker()
    for document in unrelated:
        scorer.compute_heuristic_score(document, context)
        assert document["_feats"]["study_doc"] == 0 and document["_feats"]["slide_lecture"] == 0
    scorer.compute_heuristic_score(real, context)
    assert real["_feats"]["study_doc"] > 0 and real["_feats"]["slide_lecture"] > 0
    assert _ranked("slides giải tích", unrelated + [real])[0] == real["file_name"]


def test_strong_matches_are_ordered_by_unclamped_score_not_by_the_cap():
    """Both decks clamp to 100; the one that matches more of the query must still come first."""
    weaker = _deck("Giai tich 1 - Chuong 2 slides.pptx", "đạo hàm")
    stronger = _deck("Giai tich Calculus 1 - Chuong 2 slides.pptx", "đạo hàm")
    context = ContextParser.parse_query("slides giải tích calculus")
    scorer = Reranker()
    scores = [scorer.compute_heuristic_score(dict(d), context)[0] for d in (weaker, stronger)]
    raw = []
    for d in (weaker, stronger):
        scorer.compute_heuristic_score(d, context)
        raw.append(d["_raw_score"])
    assert scores == [100.0, 100.0] and raw[1] > raw[0]
    assert _ranked("slides giải tích calculus", [weaker, stronger])[0] == stronger["file_name"]
