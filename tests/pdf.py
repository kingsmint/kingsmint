"""Write small PDFs for tests, so the repository needs no binary statements."""
import unicodedata

ACCENTS = {"ACUTE": "acute", "CARON": "caron", "DIAERESIS": "dieresis", "CIRCUMFLEX": "circumflex", "RING ABOVE": "ring"}


def glyph(c):  # "č" -> "ccaron", the Adobe glyph name a PDF reader maps back to Unicode
    letter, accent = unicodedata.name(c).split(" WITH ")
    base = letter.split()[-1]
    return (base.lower() if "SMALL" in letter else base) + ACCENTS[accent]


def make_pdf(path, font, lines):
    """Write a one-page PDF; lines are (x, y, text) in points, 10pt font."""
    extra = sorted({c for _, _, t in lines for c in t if ord(c) > 126})
    code = {c: 128 + i for i, c in enumerate(extra)}

    def pdf_str(t):
        return b"".join(b"\\%03o" % code[c] if c in code else b"\\" * (c in "()\\") + c.encode() for c in t)

    content = b"".join(b"BT /F1 10 Tf %g %g Td (%s) Tj ET\n" % (x, y, pdf_str(t)) for x, y, t in lines)
    encoding = f"<< /Type /Encoding /Differences [128 {' '.join('/' + glyph(c) for c in extra)}] >>"
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 800] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(content) + content + b"endstream",
            f"<< /Type /Font /Subtype /Type1 /BaseFont /{font} /Encoding {encoding} >>".encode()]
    out, offsets = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    path.write_bytes(out)


def text_pdf(path, text):
    """A monospaced PDF of `text`, one line per text line: pdf_text returns the same text."""
    make_pdf(path, "Courier", [(30, 780 - 12 * i, line) for i, line in enumerate(text.splitlines()) if line.strip()])
