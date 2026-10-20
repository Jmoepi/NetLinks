"""Generate the fictional NetLinks demo documents (plan A5/A6).

Usage (inside the backend container):
    python tools/generate_demo_docs.py --out /demo-assets

Output is byte-deterministic (reportlab invariant mode) because the AI cache is keyed by the
sha256 of each file. If these documents change, the AI cache must be regenerated.

Every page carries a diagonal "FICTIONAL - DEMO ONLY" watermark, a matching header line and a
fictional-document footer. Plain summary-sheet styling only: no logos, seals, crests or replicas
of vendor or government documents. Each fact is one clear sentence so source spans highlight cleanly.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

from reportlab import rl_config
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

rl_config.invariant = 1  # fixed creation date and document ID -> stable bytes

WATERMARK = "FICTIONAL - DEMO ONLY"
FOOTER = "Fictional demo document generated for the NetLinks hackathon prototype"

PAGE_W, PAGE_H = A4
MARGIN = 56
BODY_FONT = "Helvetica"
BOLD_FONT = "Helvetica-Bold"
BODY_SIZE = 10.5
LINE_H = 15


@dataclass
class Section:
    heading: str
    sentences: list[str] = field(default_factory=list)


@dataclass
class Doc:
    filename: str
    title: str
    sections: list[Section]


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _decorate_page(c: canvas.Canvas) -> None:
    """Watermark, header banner and footer, drawn on every page."""
    c.saveState()
    c.setFillGray(0.86)
    c.setFont(BOLD_FONT, 54)
    c.translate(PAGE_W / 2, PAGE_H / 2)
    c.rotate(45)
    c.drawCentredString(0, 0, WATERMARK)
    c.restoreState()

    c.saveState()
    c.setFillGray(0.35)
    c.setFont(BOLD_FONT, 9)
    c.drawString(MARGIN, PAGE_H - 36, WATERMARK)
    c.setFont(BODY_FONT, 8.5)
    c.drawString(MARGIN, 32, FOOTER)
    c.restoreState()


def render_pdf(doc: Doc, path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setTitle(doc.title)
    c.setAuthor("NetLinks demo generator (fictional)")
    c.setSubject(WATERMARK)

    width = PAGE_W - 2 * MARGIN
    y_min = 60

    def new_page() -> float:
        _decorate_page(c)
        return PAGE_H - 70

    y = new_page()
    title_lines = simpleSplit(doc.title, BOLD_FONT, 15, width)
    c.setFont(BOLD_FONT, 15)
    for line in title_lines:
        c.drawString(MARGIN, y, line)
        y -= 20
    y -= 6

    for section in doc.sections:
        needed = LINE_H * 2 + 8
        if y - needed < y_min:
            c.showPage()
            y = new_page()
        c.setFont(BOLD_FONT, 11.5)
        c.drawString(MARGIN, y, section.heading)
        y -= LINE_H + 2
        for sentence in section.sentences:
            lines = simpleSplit(sentence, BODY_FONT, BODY_SIZE, width)
            if y - LINE_H * len(lines) < y_min:
                c.showPage()
                y = new_page()
            c.setFont(BODY_FONT, BODY_SIZE)
            for line in lines:
                c.drawString(MARGIN, y, line)
                y -= LINE_H
            y -= 3
        y -= 8

    c.showPage()
    c.save()


# ---------------------------------------------------------------------------
# Document content (facts per plan A5)
# ---------------------------------------------------------------------------

NOT_REAL = "This company and every person and client named in this document are fictional."


def _clients(clients: list[tuple[str, int]]) -> list[str]:
    return [f"Client: {name} (fictional), {users} users." for name, users in clients]


def capability_thuto() -> Doc:
    return Doc(
        "Thuto_Capability_Statement.pdf",
        "Thuto Tech Solutions (fictional) - Capability Statement",
        [
            Section("Company overview", [
                "Company name: Thuto Tech Solutions.",
                "Head office: Midrand, Gauteng.",
                "Service regions: Gauteng.",
                "We have been trading for 6 years.",
                NOT_REAL,
            ]),
            Section("Services", [
                "Our services: service desk, desktop and device support, Microsoft 365 administration "
                "and network support.",
                "Service desk hours: 07:00 to 18:00, Monday to Friday.",
            ]),
            Section("Team", [
                "Our team currently has 9 field technicians.",
            ]),
            Section("Comparable clients", _clients([
                ("Kgosi Logistics", 250),
                ("Marula Health Group", 320),
                ("Highveld Property Trust", 600),
            ])),
            Section("Compliance summary", [
                "Tax compliance status: compliant, valid to 2027-06-30.",
                "CSD supplier number: MAAA0412345.",
                "Black ownership: 100% Black-owned.",
                "B-BBEE status: Level 1.",
                "Cover: R2 mil professional liability, valid to 31 August 2027.",
            ]),
        ],
    )


def capability_mmapula() -> Doc:
    # Deliberately never uses the buyer's vocabulary (semantic-match showcase).
    return Doc(
        "Mmapula_Capability_Statement.pdf",
        "Mmapula Digital Workplace (fictional) - Capability Statement",
        [
            Section("Company overview", [
                "Company name: Mmapula Digital Workplace.",
                "Head office: Soshanguve, Gauteng.",
                "Service regions: Gauteng.",
                "We have been trading for 4 years.",
                "CSD supplier number: MAAA0523456.",
                "Black ownership: 100% Black-owned.",
                "B-BBEE status: Level 1.",
                NOT_REAL,
            ]),
            Section("What we do", [
                "We offer workplace technology care for corporate teams: device lifecycle, Microsoft 365 "
                "tenant administration, remote and on-site user assistance.",
                "User assistance hours: 07:30 to 17:00, Monday to Friday.",
            ]),
            Section("Team", [
                "Our team currently has 6 field technicians.",
            ]),
            Section("Comparable clients", _clients([
                ("Tshwane Freight Partners", 220),
                ("Bophelo Medical Billing", 300),
            ])),
        ],
    )


def capability_zola() -> Doc:
    return Doc(
        "Zola_Capability_Statement.pdf",
        "Zola Systems (fictional) - Capability Statement",
        [
            Section("Company overview", [
                "Company name: Zola Systems.",
                "Head office: Soweto, Gauteng.",
                "Service regions: Gauteng.",
                "We have been trading for 3 years.",
                "CSD supplier number: MAAA0634567.",
                "Black ownership: 70% Black-owned.",
                "B-BBEE status: Level 2.",
                NOT_REAL,
            ]),
            Section("Services", [
                "Our services: desktop and device support, service desk and network cabling.",
                "Service desk hours: 08:00 to 17:00, Monday to Friday.",
            ]),
            Section("Team", [
                "Our team currently has 9 field technicians.",
            ]),
            Section("Comparable clients", _clients([
                ("Orlando Community Bank", 210),
                ("Kliptown Print Works", 80),
            ])),
        ],
    )


def capability_brightpath() -> Doc:
    return Doc(
        "BrightPath_Capability_Statement.pdf",
        "Bright Path Networks (fictional) - Capability Statement",
        [
            Section("Company overview", [
                "Company name: Bright Path Networks.",
                "Head office: Germiston, Gauteng.",
                "Service regions: Gauteng.",
                "We have been trading for 5 years.",
                "CSD supplier number: MAAA0745678.",
                "Black ownership: 60% Black-owned.",
                "B-BBEE status: Level 2.",
                NOT_REAL,
            ]),
            Section("Services", [
                "Our services: network installation, device support and service desk.",
                "Service desk hours: 07:00 to 17:00, Monday to Friday.",
            ]),
            Section("Team", [
                "Our team currently has 4 field technicians.",
            ]),
            Section("Comparable clients", _clients([
                ("Ekurhuleni Packaging Co", 230),
                ("Primrose Dental Studio", 90),
            ])),
        ],
    )


def capability_lerato() -> Doc:
    return Doc(
        "Lerato_Capability_Statement.pdf",
        "Lerato Web Studio (fictional) - Capability Statement",
        [
            Section("Company overview", [
                "Company name: Lerato Web Studio.",
                "Head office: Cape Town, Western Cape.",
                "Service regions: Western Cape only.",
                "We have been trading for 5 years.",
                "CSD supplier number: MAAA0856789.",
                "Black ownership: 100% Black-owned.",
                "B-BBEE status: Level 1.",
                NOT_REAL,
            ]),
            Section("Services", [
                "Our services: web design, SEO and WordPress hosting.",
                "Studio hours: 09:00 to 17:00, Monday to Friday.",
            ]),
            Section("Team", [
                "Our team currently has 3 field technicians.",
            ]),
            Section("Clients", _clients([
                ("Bo-Kaap Spice Traders", 15),
                ("Atlantic Surf School", 8),
            ])),
        ],
    )


CERT_NOTE = (
    "This is a plain summary prepared by the company; it is not a vendor certificate "
    "and no vendor records were checked."
)


def certifications(prefix: str, company: str, certs: list[tuple[str, str, str]]) -> Doc:
    return Doc(
        f"{prefix}_Technician_Certifications.pdf",
        f"{company} (fictional) - Technician Certification Summary",
        [
            Section("Certified technicians", [
                f"Technician: {holder} (fictional), {cert}, expires {expiry}."
                for holder, cert, expiry in certs
            ]),
            Section("Notes", [CERT_NOTE, NOT_REAL]),
        ],
    )


def infosec_policy(prefix: str, company: str, officer: str, effective: str, review: str) -> Doc:
    return Doc(
        f"{prefix}_InfoSec_POPIA_Policy.pdf",
        f"{company} (fictional) - Information Security and POPIA Policy",
        [
            Section("Purpose", [
                f"This policy sets out how {company} protects client information and personal information.",
                "We process personal information in line with the Protection of Personal Information Act "
                "(POPIA).",
            ]),
            Section("Responsibilities", [
                f"Information Officer: {officer} (fictional).",
                "Every staff member signs a confidentiality undertaking before accessing client systems.",
            ]),
            Section("Controls", [
                "Access to client systems uses named accounts with multi-factor authentication.",
                "Client data is stored only on encrypted company devices or client-approved systems.",
                "Security incidents are reported to the client within 72 hours.",
                "Personal information is deleted or returned when a contract ends.",
            ]),
            Section("Review", [
                f"Effective date: {effective}.",
                f"Next review date: {review}.",
                NOT_REAL,
            ]),
        ],
    )


def pi_schedule(
    filename: str,
    company: str,
    policy_no: str,
    amount: str,
    start: str,
    end: str,
    issued: str,
    title_suffix: str = "",
) -> Doc:
    return Doc(
        filename,
        f"{company} (fictional) - Professional Indemnity Insurance Schedule{title_suffix}",
        [
            Section("Schedule details", [
                f"Insured: {company} (fictional).",
                "Insurer: Sizwe Mutual Insurance (fictional).",
                f"Policy number: {policy_no}.",
                "Cover type: professional indemnity.",
                f"Limit of indemnity: {amount}.",
                f"Cover starts: {start}.",
                f"Cover expires: {end}.",
                f"Date issued: {issued}.",
            ]),
            Section("Notes", [
                "This schedule is a fictional summary for demonstration and is not an insurance contract.",
                NOT_REAL,
            ]),
        ],
    )


def tax_letter(prefix: str, company: str, ref: str, expiry: str, issued: str) -> Doc:
    return Doc(
        f"{prefix}_Tax_Compliance_Letter.pdf",
        "Tax compliance status summary (fictional)",
        [
            Section("Summary", [
                f"Taxpayer: {company} (fictional).",
                f"Reference number: {ref}.",
                "Tax compliance status: compliant.",
                f"Status valid until: {expiry}.",
                f"Date issued: {issued}.",
            ]),
            Section("Notes", [
                "This is a fictional summary for demonstration and was not issued by any revenue authority.",
                NOT_REAL,
            ]),
        ],
    )


def all_documents() -> list[Doc]:
    return [
        # Capability statements
        capability_thuto(),
        capability_mmapula(),
        capability_zola(),
        capability_brightpath(),
        capability_lerato(),
        # Technician certification summaries (current = expiry after closing date 2027-02-26)
        certifications("Thuto", "Thuto Tech Solutions", [
            ("Sipho Ndlovu", "CompTIA A+", "2028-03-31"),
            ("Lindiwe Mokoena", "Microsoft 365 Certified", "2027-09-30"),
            ("Kabelo Dube", "ITIL 4 Foundation", "2029-01-31"),
            ("Ayanda Khumalo", "CompTIA Network+", "2026-05-31"),
        ]),
        certifications("Mmapula", "Mmapula Digital Workplace", [
            ("Refilwe Mahlangu", "Microsoft 365 Certified", "2027-11-30"),
            ("Tumelo Sithole", "CompTIA A+", "2028-06-30"),
            ("Nomsa Baloyi", "ITIL 4 Foundation", "2028-12-31"),
        ]),
        certifications("Zola", "Zola Systems", [
            ("Mandla Zulu", "CompTIA A+", "2027-10-31"),
            ("Palesa Nkosi", "ITIL 4 Foundation", "2028-04-30"),
        ]),
        certifications("BrightPath", "Bright Path Networks", [
            ("Thabo Molefe", "CompTIA Network+", "2027-08-31"),
            ("Zanele Mthembu", "CompTIA A+", "2028-02-29"),
        ]),
        certifications("Lerato", "Lerato Web Studio", [
            ("Karabo Petersen", "CompTIA A+", "2027-12-31"),
            ("Aisha Jacobs", "ITIL 4 Foundation", "2028-05-31"),
        ]),
        # Information security & POPIA policies
        infosec_policy("Thuto", "Thuto Tech Solutions", "Lebo Maseko", "2026-03-01", "2027-03-01"),
        infosec_policy("Mmapula", "Mmapula Digital Workplace", "Kagiso Mabena", "2026-02-01", "2027-02-01"),
        infosec_policy("Zola", "Zola Systems", "Sibusiso Mkhize", "2026-01-15", "2027-01-15"),
        infosec_policy(
            "BrightPath", "Bright Path Networks", "Boitumelo Shabalala", "2026-04-01", "2027-04-01"
        ),
        infosec_policy("Lerato", "Lerato Web Studio", "Fatima Adams", "2026-05-01", "2027-05-01"),
        # Professional indemnity schedules (Thuto's PI is in its capability statement)
        pi_schedule("Mmapula_PI_Insurance_Schedule.pdf", "Mmapula Digital Workplace", "PI-MDW-2026-0042",
                    "R3,000,000", "2026-01-01", "2027-12-31", "2025-12-15"),
        pi_schedule("Zola_PI_Insurance_Schedule.pdf", "Zola Systems", "PI-ZS-2026-0117",
                    "R2,500,000", "2026-02-17", "2027-02-16", "2026-02-10"),
        pi_schedule("Zola_PI_Insurance_Schedule_Renewed.pdf", "Zola Systems", "PI-ZS-2027-0117",
                    "R2,500,000", "2027-02-17", "2028-02-16", "2026-10-01", " (Renewal)"),
        pi_schedule("BrightPath_PI_Insurance_Schedule.pdf", "Bright Path Networks", "PI-BPN-2026-0230",
                    "R2,000,000", "2026-07-01", "2027-06-30", "2026-06-20"),
        pi_schedule("Lerato_PI_Insurance_Schedule.pdf", "Lerato Web Studio", "PI-LWS-2026-0308",
                    "R2,000,000", "2026-10-01", "2027-09-30", "2026-09-20"),
        # Tax compliance status summaries (Thuto's is in its capability statement)
        tax_letter("Mmapula", "Mmapula Digital Workplace", "TCS-MDW-55120", "2027-09-30", "2026-09-30"),
        tax_letter("Zola", "Zola Systems", "TCS-ZS-55231", "2027-05-31", "2026-05-31"),
        tax_letter("BrightPath", "Bright Path Networks", "TCS-BPN-55342", "2027-04-30", "2026-04-30"),
        tax_letter("Lerato", "Lerato Web Studio", "TCS-LWS-55453", "2027-08-31", "2026-08-31"),
    ]


RFQ_FILENAME = "Ubuntu_Office_Parks_RFQ_raw.txt"

RFQ_TEXT = """\
REQUEST FOR QUOTATION (FICTIONAL - DEMO ONLY)

Buyer: Ubuntu Office Parks (fictional)
Contact: Naledi, Procurement (fictional)
Title: Managed IT support & end-user computing: 450 users, 3 sites (Midrand, Centurion, Sandton), \
36-month contract, 4-hour on-site response SLA
Closing date: 2027-02-26
Contract start: 2027-04-01

Background
Ubuntu Office Parks is looking for a small or medium IT company to look after about 450 users across \
our three office parks in Midrand, Centurion and Sandton. The contract runs for 36 months. We expect \
an engineer on site within 4 hours of a priority call being logged.

What every bidder must have
Bidders must hold a valid tax compliance status that remains valid after the closing date. Bidders \
must be registered on the Central Supplier Database (CSD) and give their CSD supplier number. Bidders \
must be at least 51% Black-owned or hold a B-BBEE Level 1 or Level 2 status. Bidders must operate in \
Gauteng. Bidders must hold professional indemnity insurance of at least R1 million that is still \
current at the closing date. Because the supplier will handle our staff's personal information, \
bidders must provide an information security and POPIA policy. Bidders must have at least two \
technicians with current certifications, for example CompTIA A+, Microsoft 365 Certified or ITIL 4 \
Foundation.

What we would like to see
We would prefer a supplier with proven service desk, desktop and device support, and Microsoft 365 \
administration capability. We would prefer at least 3 years of trading and experience with comparable \
clients of 200 or more users. We would prefer a team of 8 or more technicians and service desk hours \
that cover 07:00 to 18:00 on weekdays. Because of the 4-hour on-site response time, we would prefer a \
supplier based within about 50 km of our Midrand site.

This request for quotation and the buyer named in it are fictional and were written for the NetLinks \
hackathon prototype demo.
"""


def expected_filenames() -> list[str]:
    return sorted([d.filename for d in all_documents()] + [RFQ_FILENAME])


def generate(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for doc in all_documents():
        path = out_dir / doc.filename
        render_pdf(doc, path)
        written.append(path)
    rfq_path = out_dir / RFQ_FILENAME
    rfq_path.write_bytes(RFQ_TEXT.encode("utf-8"))  # exact bytes, LF line endings
    written.append(rfq_path)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, help="Output directory (e.g. /demo-assets)")
    args = parser.parse_args()
    written = generate(Path(args.out))
    for path in written:
        print(path)
    print(f"Wrote {len(written)} files.")


if __name__ == "__main__":
    main()
