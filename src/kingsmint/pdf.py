import ctypes

import pypdfium2
import pypdfium2.raw as pdfium


def pdf_text(path):
    """Text of a PDF with the page layout kept: each word at a column proportional to its x position.

    On a monospaced page, each word is at its exact column. Otherwise, words closer than 1.5 characters are one phrase, separated by one space; farther words are
    separated by at least two spaces, so table columns stay apart. Vertical text (side margins) is left out.
    """
    pdf = pypdfium2.PdfDocument(path)
    try:
        return "\n\f".join(page_text(page) for page in pdf)
    finally:
        pdf.close()  # Windows: the file cannot be moved while it is open


def page_text(page):
    tp, height = page.get_textpage(), page.get_height()
    chars = []  # (top, x0, x1, text) of upright characters
    for i in range(tp.count_chars()):
        if pdfium.FPDFText_IsGenerated(tp.raw, i) or pdfium.FPDFText_GetCharAngle(tp.raw, i) > 0.01:
            continue
        x0, _, x1, _ = tp.get_charbox(i, loose=True)
        x, y = ctypes.c_double(), ctypes.c_double()
        pdfium.FPDFText_GetCharOrigin(tp.raw, i, x, y)  # the baseline: box tops differ between characters
        text = "-" if pdfium.FPDFText_IsHyphen(tp.raw, i) else chr(pdfium.FPDFText_GetUnicode(tp.raw, i))
        chars.append((height - y.value, x0, x1, text))
    lines = []  # [top, chars]
    for c in sorted(chars, key=lambda c: (round(c[0]), c[1])):
        if lines and abs(c[0] - lines[-1][0]) < 2:
            lines[-1][1].append(c)
        else:
            lines.append([c[0], [c]])
    words = []  # per line: [x0, x1, text]; a word ends at a space or a gap wider than 1.5 points
    for _, cs in lines:
        ws, gap = [], True
        for _, x0, x1, text in sorted(cs, key=lambda c: c[1]):
            if not text.strip():
                gap = True
            elif not gap and x0 <= ws[-1][1] + 1.5:
                ws[-1][1:] = [x1, ws[-1][2] + text]
            else:
                ws.append([x0, x1, text])
                gap = False
        words.append(ws)
    widths = [x1 - x0 for _, x0, x1, text in chars if text.strip()]
    if not widths:
        return ""
    mono = max(widths) - min(widths) < 0.01  # a monospaced page: columns are exact
    flat = [w for ws in words for w in ws]
    cw = widths[0] if mono else 1.2 * sum(x1 - x0 for x0, x1, _ in flat) / sum(len(t) for _, _, t in flat)
    left = min(x0 for x0, _, _ in flat)
    out = []
    for ws in words:
        line, prev = "", None
        for x0, x1, text in ws:
            if prev is not None and not mono and (x0 - prev) / cw <= 1.5:  # same phrase: one space
                line += " " + text
            else:
                line += " " * max(round((x0 - left) / cw) - len(line), 0 if prev is None else 1 if mono else 2) + text
            prev = x1
        out.append(line)
    return "\n".join(out)
