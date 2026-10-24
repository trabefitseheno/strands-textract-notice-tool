"""Generate 3 synthetic notices (invented town, no real people). Run: python samples/make_samples.py"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

OUT = Path(__file__).parent
NOTICES = {
    "water_shutoff": [
        "TOWN OF RIVERBEND - PUBLIC NOTICE", "",
        "Water service interruption", "",
        "Water will be shut off on Tuesday, 12 May 2026",
        "from 8:00 AM to 2:00 PM on Maple Street and Oak Lane.",
        "Residents may collect free water at Riverbend Hall.",
        "Questions: call 555-0142.",
    ],
    "permit_deadline": [
        "RIVERBEND PLANNING OFFICE", "",
        "Notice of building permit deadline", "",
        "Owners of properties on Elm Road must file Form B-7",
        "by 30 June 2026. The filing fee is $85.00.",
        "Late filings pay a surcharge of $20.00.",
        "Apply at 14 Council Square, Room 3.",
    ],
    "clinic_hours": [
        "RIVERBEND COMMUNITY CLINIC", "",
        "Free flu vaccination days", "",
        "Residents aged 65 and over may attend on Saturday",
        "17 October 2026, 9:00 AM to 1:00 PM, at the Library Annex.",
        "Bring a photo ID. No appointment needed.",
        "Helpline: 555-0177.",
    ],
}


def font(size):
    for p in ("/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def image(name, lines, photo=False):
    img = Image.new("RGB", (1000, 700), "white")
    d = ImageDraw.Draw(img)
    y = 50
    for i, ln in enumerate(lines):
        d.text((60, y), ln, fill="black", font=font(34 if i == 0 else 28))
        y += 56
    if photo:  # mild "phone photo" degradation
        img = img.rotate(1.5, expand=True, fillcolor="white").filter(ImageFilter.GaussianBlur(0.8))
    img.save(OUT / f"{name}.png")


def pdf(name, lines):
    c = canvas.Canvas(str(OUT / f"{name}.pdf"), pagesize=letter)
    y = 720
    for ln in lines:
        c.setFont("Helvetica-Bold" if y == 720 else "Helvetica", 16)
        c.drawString(72, y, ln)
        y -= 30
    c.save()


if __name__ == "__main__":
    image("water_shutoff", NOTICES["water_shutoff"])
    image("permit_deadline", NOTICES["permit_deadline"], photo=True)
    pdf("clinic_hours", NOTICES["clinic_hours"])
    (OUT / "plain_text.txt").write_text("\n".join(NOTICES["water_shutoff"]) + "\n")
    print("wrote samples")
