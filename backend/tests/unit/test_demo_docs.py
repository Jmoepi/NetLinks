import hashlib
import re
from datetime import date, timedelta
from pathlib import Path

import pytest
from pypdf import PdfReader

from app.config import get_settings
from tools.generate_demo_docs import RFQ_FILENAME, WATERMARK, expected_filenames, generate

CLOSING_DATE = date(2027, 2, 26)
ASSETS = Path(get_settings().demo_assets_dir)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pages(path: Path) -> list[str]:
    return [page.extract_text() or "" for page in PdfReader(str(path)).pages]


def _text(name: str) -> str:
    return "\n".join(_pages(ASSETS / name))


@pytest.fixture(scope="module")
def regenerated(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("demo-assets")
    generate(out)
    return out


def test_expected_file_list_is_complete(regenerated):
    names = expected_filenames()
    assert len([n for n in names if n.endswith(".pdf")]) == 24
    assert RFQ_FILENAME in names
    assert sorted(p.name for p in regenerated.iterdir()) == names
    assert sorted(p.name for p in ASSETS.iterdir() if not p.name.startswith(".")) == names


def test_regeneration_is_byte_identical(regenerated):
    for name in expected_filenames():
        assert _sha256(regenerated / name) == _sha256(ASSETS / name), name


@pytest.mark.parametrize("name", [n for n in expected_filenames() if n.endswith(".pdf")])
def test_every_page_is_watermarked(name):
    pages = _pages(ASSETS / name)
    assert pages
    for page_text in pages:
        assert WATERMARK in page_text


def test_mmapula_avoids_buyer_vocabulary():
    text = _text("Mmapula_Capability_Statement.pdf").lower()
    for phrase in ("it support", "service desk", "managed services"):
        assert phrase not in text
    assert "workplace technology care for corporate teams" in " ".join(text.split())


def test_brightpath_states_four_technicians():
    assert re.search(r"\b4 field technicians\b", _text("BrightPath_Capability_Statement.pdf"))


def test_zola_pi_expires_ten_days_before_closing():
    match = re.search(r"Cover expires: (\d{4}-\d{2}-\d{2})", _text("Zola_PI_Insurance_Schedule.pdf"))
    assert match
    assert date.fromisoformat(match.group(1)) == CLOSING_DATE - timedelta(days=10)


def test_zola_renewed_pi_covers_contract_start():
    text = _text("Zola_PI_Insurance_Schedule_Renewed.pdf")
    assert "Cover starts: 2027-02-17." in text
    assert "Cover expires: 2028-02-16." in text
    assert "Date issued: 2026-10-01." in text


def test_thuto_capability_holds_compliance_summary():
    text = " ".join(_text("Thuto_Capability_Statement.pdf").split())
    for sentence in (
        "Our team currently has 9 field technicians.",
        "R2 mil professional liability, valid to 31 August 2027",
        "MAAA0412345",
        "100% Black-owned",
        "Level 1",
        "2027-06-30",
    ):
        assert sentence in text


def test_rfq_mentions_r1_million_and_closing_date():
    text = (ASSETS / RFQ_FILENAME).read_text(encoding="utf-8")
    assert "R1 million" in text
    assert "2027-02-26" in text
