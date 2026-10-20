"""Headers and demo-asset helpers shared by the HTTP-level tests."""

from pathlib import Path

from app.config import get_settings

BUYER = {"X-Demo-Role": "buyer"}
ADMIN = {"X-Demo-Role": "admin"}
THUTO_FILES = [
    "Thuto_Capability_Statement.pdf",
    "Thuto_Technician_Certifications.pdf",
    "Thuto_InfoSec_POPIA_Policy.pdf",
]


def as_sme(slug: str) -> dict[str, str]:
    return {"X-Demo-Role": "sme", "X-Demo-Sme-Id": slug}


def asset(name: str) -> bytes:
    return (Path(get_settings().demo_assets_dir) / name).read_bytes()


def pdf_files(*names: str) -> list[tuple[str, tuple[str, bytes, str]]]:
    return [("files", (n, asset(n), "application/pdf")) for n in names]
