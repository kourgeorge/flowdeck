"""
Tests for deterministic heading-anchor section extraction.

Guards the two cases sec2md cannot slice - a 20-F whose pages its splitter collapses
into one (TSM/ASML) and a 40-F wrapper whose narrative lives in EX-* exhibits with no
ITEM headings at all - plus the table-of-contents false positives that a naive
first-match `re.search` picks up.

All text is synthetic; no network, no LLM.
"""
import pytest

from ai_engine.tradingagents.agents.utils.sec_file_explorer import SECFilingExplorer
from ai_engine.tradingagents.agents.utils.sec_section_anchors import (
    SECTION_KEYS,
    extract_all_sections,
    extract_section,
)

FILLER = "The disclosure continues with substantive narrative text. "


def _body(times: int = 30) -> str:
    return FILLER * times


TEN_K = f"""
TABLE OF CONTENTS

Item 1. Business ....... 3
Item 1A. Risk Factors ....... 9
Item 3. Legal Proceedings ....... 25
Item 7. Management's Discussion and Analysis ....... 30
Item 7A. Quantitative and Qualitative Disclosures About Market Risk ....... 55

PART I

Item 1. Business

We design and sell consumer electronics. {_body()}

Competition

The markets for our products are highly competitive. {_body()}

Item 1A. Risk Factors

Our business is subject to the following risks. {_body()}

Item 3. Legal Proceedings

We are party to various legal proceedings. {_body()}

Item 7. Management's Discussion and Analysis of Financial Condition

Net sales increased year over year. {_body()}

Item 7A. Quantitative and Qualitative Disclosures About Market Risk

We are exposed to interest rate risk. {_body()}

Item 8. Financial Statements and Supplementary Data
"""

TWENTY_F = f"""
| Item 3. Key Information | 12 |
| Item 4. Information on the Company | 30 |
| Item 5. Operating and Financial Review and Prospects | 40 |

ITEM 3. KEY INFORMATION

A. Selected Financial Data

Revenue was NT$2.2 trillion. {_body()}

D. Risk Factors

Concentration of manufacturing in one region is a risk. {_body()}

ITEM 4. INFORMATION ON THE COMPANY

We are the largest dedicated foundry. {_body()}

ITEM 5. OPERATING AND FINANCIAL REVIEW AND PROSPECTS

Gross margin was 54 percent. {_body()}

ITEM 11. QUANTITATIVE AND QUALITATIVE DISCLOSURES ABOUT MARKET RISK

We hedge foreign currency exposure. {_body()}

ITEM 12. DESCRIPTION OF SECURITIES OTHER THAN EQUITY SECURITIES
"""

# A 40-F exhibit (Canadian AIF/MD&A): markdown headings, no ITEM numbering anywhere.
FORTY_F_EXHIBIT = f"""# Annual Information Form

## Management\u2019s Discussion and Analysis

Adjusted EBITDA rose eight percent. {_body()}

## Legal Proceedings

We are party to routine litigation incidental to our business. {_body(3)}

## Financial Risk Management

We use derivatives to manage commodity price risk. {_body()}
"""

# A pre-2018 40-F exhibit bundle: Canadian AIF (NI 51-102) headings, quadruple-asterisk
# emphasis instead of markdown headings, and Windows-1252 apostrophes (\x92) that survive
# EDGAR's latin-1 decoding.
FORTY_F_LEGACY = f"""****GENERAL DESCRIPTION OF THE BUSINESS****

We operate liquids pipelines across North America. {_body()}

****Competition****

Energy Services earnings depend on arbitrage opportunities. {_body()}

****RISK FACTORS****

A discussion of the Company\x92s risk factors follows. {_body()}

****LEGAL PROCEEDINGS AND REGULATORY ACTIONS****

Information related to the Company\x92s proceedings follows. {_body()}

****MANAGEMENT\x92S DISCUSSION AND ANALYSIS****

This Management\x92s Discussion and Analysis is dated February 17. {_body()}

****MARKET RISK****

We are exposed to commodity price and interest rate risk. {_body()}
"""

# An integrated (IFRS-style) annual report filed as a 20-F: no ITEM headings, and the
# MD&A/business sections are named the way the filer's own Item cross-reference table
# maps them. Includes the bolded mid-sentence fragment that must NOT anchor a section.
INTEGRATED_20F = f"""**Our business strategy**

Six priorities drive long-term growth. {_body()}

**Financial performance KPIs**

Total net sales grew twelve percent. {_body()}

**Risk factors**

The risk factors below are categorized by type. {_body()}

**Appendix - Reference table 20-F**

| Item | Form 20-F caption | Location | Page |
| --- | --- | --- | --- |
| 3 | Key information | Risk - Risk factors | 66 |
| 5 | Operating and Financial Review and Prospects | Financial performance | 54 |

The Board acts in the long-term interest of **our business - and takes into
consideration** the interests of our stakeholders. {_body()}
"""


# ---------------------------------------------------------------- TOC rejection


def test_toc_entries_with_dot_leaders_are_rejected():
    hit = extract_section(TEN_K, "risk_factors", form="10-K")
    assert hit is not None
    # The TOC entry sits before "PART I"; the real heading comes after it.
    assert hit.start > TEN_K.index("PART I")
    assert "Our business is subject to the following risks." in hit.text


def test_markdown_table_of_contents_rows_are_rejected():
    hit = extract_section(TWENTY_F, "management_mda", form="20-F")
    assert hit is not None
    assert "|" not in hit.matched_heading
    assert "Gross margin was 54 percent." in hit.text


def test_inline_cross_reference_is_not_a_section_start():
    text = "Our results may suffer; see Item 1A. Risk Factors for details. " + _body()
    assert extract_section(text, "risk_factors", form="10-K") is None


# ---------------------------------------------------------------- boundaries


def test_section_ends_at_next_item_heading():
    hit = extract_section(TEN_K, "market_risk_disclosures", form="10-K", max_chars=100_000)
    assert hit is not None
    assert "interest rate risk" in hit.text
    assert "Financial Statements and Supplementary Data" not in hit.text
    assert not hit.truncated


def test_item_section_spans_its_nested_subheadings():
    """Item 1 Business runs to Item 1A, keeping the nested Competition subsection."""
    business = extract_section(TEN_K, "business_overview", form="10-K", max_chars=100_000)
    assert business is not None
    assert "The markets for our products are highly competitive." in business.text
    assert "Our business is subject to the following risks." not in business.text

    # ...and Competition is still available on its own.
    competition = extract_section(TEN_K, "competition", form="10-K")
    assert competition is not None
    assert competition.matched_heading.strip() == "Competition"


def test_truncation_is_flagged_and_capped():
    hit = extract_section(TEN_K, "risk_factors", form="10-K", max_chars=200)
    assert hit is not None
    assert hit.truncated
    assert len(hit.text) <= 200


# ---------------------------------------------------------------- per-form


def test_ten_k_sections_all_found():
    sections = extract_all_sections(TEN_K, form="10-K")
    for key in SECTION_KEYS:
        assert sections[key], f"{key} not extracted"


def test_ten_k_item_3_is_legal_proceedings_not_risk_factors():
    """A 10-K's Item 3 is Legal Proceedings; the 20-F Item 3 anchor must stay gated."""
    sections = extract_all_sections(TEN_K, form="10-K")
    assert "We are party to various legal proceedings." in sections["legal_proceedings"]
    assert "We are party to various legal proceedings." not in sections["risk_factors"]


@pytest.mark.parametrize(
    "key,needle",
    [
        ("risk_factors", "Concentration of manufacturing"),
        ("business_overview", "largest dedicated foundry"),
        ("management_mda", "Gross margin was 54 percent"),
        ("market_risk_disclosures", "hedge foreign currency exposure"),
    ],
)
def test_twenty_f_items(key, needle):
    sections = extract_all_sections(TWENTY_F, form="20-F", max_chars=100_000)
    assert needle in sections[key]


def test_forty_f_exhibit_without_items():
    sections = extract_all_sections(FORTY_F_EXHIBIT, form="40-F")
    assert "Adjusted EBITDA rose eight percent." in sections["management_mda"]
    assert "routine litigation" in sections["legal_proceedings"]
    assert "commodity price risk" in sections["market_risk_disclosures"]


def test_legacy_forty_f_exhibit_all_sections():
    """Canadian AIF vocabulary, ****CAPS**** emphasis, Windows-1252 apostrophes."""
    sections = extract_all_sections(FORTY_F_LEGACY, form="40-F", max_chars=100_000)
    for key in SECTION_KEYS:
        assert sections[key], f"{key} not extracted"
    assert "liquids pipelines" in sections["business_overview"]
    assert "dated February 17" in sections["management_mda"]
    assert "commodity price and interest rate risk" in sections["market_risk_disclosures"]


def test_twenty_f_item_4_accepts_filer_named_caption():
    """Filers rename the Form 20-F caption after themselves: "INFORMATION ABOUT SAP"."""
    text = f"ITEM 4. INFORMATION ABOUT SAP\n\nWe sell enterprise software. {_body()}\n"
    hit = extract_section(text, "business_overview", form="20-F")
    assert hit is not None
    assert "enterprise software" in hit.text


def test_hard_wrapped_sentence_is_not_a_heading():
    """Print-derived filings wrap prose; a lowercase continuation must not anchor."""
    text = (
        "These include the sustainability-related risks and opportunities affecting our\n\n"
        f"competitive position and long-term\n\nshareholder value creation. {_body()}\n"
    )
    assert extract_section(text, "competition", form="20-F") is None


def test_integrated_annual_report_without_items():
    """ASML-shaped 20-F: no ITEM headings, integrated-report section names."""
    sections = extract_all_sections(INTEGRATED_20F, form="20-F", max_chars=100_000)
    assert "Six priorities drive long-term growth." in sections["business_overview"]
    assert "Total net sales grew twelve percent." in sections["management_mda"]
    assert "categorized by type" in sections["risk_factors"]


def test_bold_prose_fragment_is_not_a_keyword_heading():
    """A bare-keyword anchor must end its line; bolded mid-sentence text must not win."""
    hit = extract_section(INTEGRATED_20F, "business_overview", form="20-F")
    assert hit is not None
    assert hit.matched_heading.strip() == "**Our business strategy**"


def test_junk_text_yields_no_sections():
    sections = extract_all_sections("Exhibit 32.1 CERTIFICATION\nSigned by the CEO.\n", form="6-K")
    assert not any(sections.values())


def test_unknown_form_still_extracts():
    """form=None must not gate out the item anchors."""
    sections = extract_all_sections(TEN_K, form=None)
    assert sections["risk_factors"]
    assert sections["management_mda"]


# ---------------------------------------------------------------- explorer


def test_explorer_find_section_aliases():
    explorer = SECFilingExplorer(TEN_K, {"form": "10-K"})
    assert "highly competitive" in (explorer.find_section("competition") or "")
    assert "Net sales increased" in (explorer.find_section("mda") or "")
    assert "consumer electronics" in (explorer.find_section("business") or "")
    assert "interest rate risk" in (explorer.find_section("market_risk") or "")
    assert explorer.find_section("not_a_section") is None


def test_explorer_marks_truncated_sections():
    explorer = SECFilingExplorer(TEN_K, {"form": "10-K"})
    out = explorer.find_section("risk_factors", max_chars=300)
    assert out is not None
    assert out.endswith("... (truncated)")


# ---------------------------------------------------------------- service wiring


def _service(monkeypatch, markdown, sec2md_result):
    """
    EdgarService with one filing and stubbed document fetch.

    `svc.llm_calls` counts LLM-fallback attempts. The service swallows extraction
    errors, so raising here would be invisible - we count instead.
    """
    from backend.services.edgar_service import EdgarService

    svc = EdgarService()
    svc.llm_calls = 0
    monkeypatch.setattr(
        svc,
        "get_filings",
        lambda ticker: {
            "cik": "1046179",
            "error": None,
            "filings": [
                {
                    "form": "20-F",
                    "filing_date": "2025-04-16",
                    "accession_number": "0001046179-25-000021",
                    "url": "https://example.invalid/primary.htm",
                }
            ],
        },
    )
    monkeypatch.setattr(svc, "_fetch_filing_documents", lambda *a, **k: ["<html></html>"])
    monkeypatch.setattr(svc, "_html_to_markdown", lambda *a, **k: markdown)
    monkeypatch.setattr(svc, "_extract_sections_sec2md", lambda *a, **k: sec2md_result)

    def _count_llm():
        svc.llm_calls += 1
        raise RuntimeError("no LLM in tests")

    monkeypatch.setattr(svc, "_get_extraction_llm", _count_llm)
    return svc


def test_anchors_fill_sections_when_sec2md_finds_nothing(monkeypatch):
    svc = _service(monkeypatch, TWENTY_F, None)
    result = svc.get_filing_content("TSM", form="20-F", limit=1)
    sections = result["filings"][0]["sections"]
    assert "Gross margin was 54 percent" in sections["management_mda"]
    assert "Concentration of manufacturing" in sections["risk_factors"]
    assert svc.llm_calls == 0


def test_anchors_only_fill_keys_sec2md_left_empty(monkeypatch):
    partial = {k: "" for k in SECTION_KEYS}
    partial["risk_factors"] = "SEC2MD RISK TEXT"
    svc = _service(monkeypatch, TWENTY_F, partial)

    sections = svc.get_filing_content("TSM", form="20-F", limit=1)["filings"][0]["sections"]
    assert sections["risk_factors"] == "SEC2MD RISK TEXT"
    assert "Gross margin was 54 percent" in sections["management_mda"]
    assert svc.llm_calls == 0


def test_llm_fallback_runs_when_nothing_deterministic_found(monkeypatch):
    svc = _service(monkeypatch, "Exhibit 99.1 Press release. Nothing anchorable here.", None)
    monkeypatch.setattr(svc, "_html_to_text", lambda *a, **k: "press release body")
    svc.get_filing_content("TSM", form="20-F", limit=1)
    assert svc.llm_calls == 1
