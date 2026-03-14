"""
Lexora PDF Reader

Extracts text from exam PDFs and removes obvious layout artifacts.
Avoids aggressive cleaning that may destroy meaningful numbers.
"""

from typing import List
from pathlib import Path
import re
import pdfplumber

try:
    import pytesseract
    import fitz  # PyMuPDF
    from PIL import Image
    import io
    # Point pytesseract at the default Windows install location
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False



GRAPH_LINE_PATTERN = re.compile(
    r"^\d+\s*(million|billion|thousand)?\s*(tonnes|tons|t o n n e s|%)\b",
    re.IGNORECASE
)

AXIS_LABEL_PATTERN = re.compile(r"^\d{4}(\s+\d{4}){2,}$")

GRAPH_HEADER_PHRASES = [
    "global plastics production",
    "measured in metric tonnes",
    "polymer resin and fiber",
    "in data",
    "our world",
]

SECTION_MARKER_PATTERN = re.compile(
    r"^\(?(Reading|Writing|Literature)\)?\s*\(\d+\s*marks?\)",
    re.IGNORECASE
)


def _is_graph_line(line: str) -> bool:
    lower = line.lower().strip()

    if GRAPH_LINE_PATTERN.match(line.strip()):
        return True

    if AXIS_LABEL_PATTERN.match(line.strip()):
        return True

    for phrase in GRAPH_HEADER_PHRASES:
        if phrase in lower:
            return True

    # Bare unit lines like "0 t o n n e s"
    if re.match(r"^0\s+t\s+o\s+n\s+n\s+e\s+s$", line.strip()):
        return True

    return False


def _clean_page_text(text: str) -> str:
    """
    Remove only clear layout artifacts while preserving semantic content.
    """

    lines = text.split("\n")

    cleaned_lines = []

    for line in lines:

        line = line.strip()

        if not line:
            continue

        # Remove page markers like ".1/2/2"
        if re.match(r"^\.\d+/\d+/\d+", line):
            continue

        # Remove page counters like "1 /2/2"
        if re.match(r"^\d+\s*/\d+/\d+", line):
            continue

        # Remove footer markers
        if "P.T.O." in line:
            continue

        # Remove obvious header labels
        if "Q.P. Code" in line:
            continue

        if line.startswith("Series"):
            continue

        if line.startswith("Roll No"):
            continue

        # Remove section markers like "SECTION A", "(Reading) (14 marks)"
        if re.match(r"^SECTION\s+[A-Z]$", line):
            continue

        if SECTION_MARKER_PATTERN.match(line):
            continue

        # Remove graph/chart artifacts
        if _is_graph_line(line):
            continue

        # Remove standalone "World" label from graphs
        if line.strip() == "World":
            continue

        # Normalize whitespace only
        line = re.sub(r"\s+", " ", line)

        cleaned_lines.append(line.strip())

    return "\n".join(cleaned_lines)


def _extract_text_from_words(page) -> str:
    """
    Fallback extraction using word-level data.
    Groups words into lines by vertical position and joins them.
    Handles cases where extract_text() drops or misaligns words.
    """

    words = page.extract_words()

    if not words:
        return ""

    # Group words by vertical position (top coordinate)
    # Words within 3 units vertically are on the same line
    lines_dict = {}

    for w in words:
        top = round(w["top"])

        # Find existing line within tolerance
        matched_top = None
        for existing_top in lines_dict:
            if abs(existing_top - top) <= 3:
                matched_top = existing_top
                break

        if matched_top is not None:
            lines_dict[matched_top].append(w)
        else:
            lines_dict[top] = [w]

    # Sort lines by vertical position, words by horizontal position
    sorted_lines = []

    for top in sorted(lines_dict.keys()):
        line_words = sorted(lines_dict[top], key=lambda w: w["x0"])
        line_text = " ".join(w["text"] for w in line_words)
        sorted_lines.append(line_text)

    return "\n".join(sorted_lines)


def _fix_ocr_subquestion_labels(text: str) -> str:
    """
    Fix common Tesseract misreads of Roman numeral subquestion labels.
    e.g. 'Gi)' → '(ii)', 'Gil)' → '(iii)', 'Gii)' → '(iii)'
    Also strips stray pipe characters that appear after misread labels.
    """
    lines = text.split("\n")
    fixed = []
    # Map of OCR artifact → correct label
    ocr_fixes = [
        (re.compile(r'^Gi\)'), '(ii)'),
        (re.compile(r'^Gii\)'), '(iii)'),
        (re.compile(r'^Gil\)'), '(iii)'),
        (re.compile(r'^Giv\)'), '(iv)'),
        (re.compile(r'^Gv\)'), '(v)'),
        (re.compile(r'^Gvi\)'), '(vi)'),
    ]
    for line in lines:
        stripped = line.strip()
        for pattern, replacement in ocr_fixes:
            if pattern.match(stripped):
                stripped = pattern.sub(replacement, stripped)
                # Remove stray pipe noise after label: "(ii) | text" → "(ii) text"
                stripped = re.sub(r'^\(([ivx]+)\)\s*\|\s*', r'(\1) ', stripped)
                break
        fixed.append(stripped)
    return "\n".join(fixed)


def _ocr_page(pil_image) -> str:
    """
    Run Tesseract OCR on a PIL image of a PDF page.
    Returns empty string if OCR is unavailable or fails.
    """
    if not OCR_AVAILABLE:
        return ""
    try:
        text = pytesseract.image_to_string(pil_image, lang='eng', config='--psm 6')
        return _fix_ocr_subquestion_labels(text)
    except Exception as e:
        return ""


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract full cleaned text from a PDF file.
    Uses OCR as a supplement when pdfplumber misses text (e.g. image-embedded lines).
    """

    pdf_file = Path(pdf_path)

    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    # Pre-render all pages to images for OCR (if available)
    page_images = []
    if OCR_AVAILABLE:
        try:
            doc = fitz.open(str(pdf_file))
            for page in doc:
                mat = fitz.Matrix(200 / 72, 200 / 72)  # 200 DPI
                pix = page.get_pixmap(matrix=mat)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                page_images.append(img)
            doc.close()
        except Exception as e:
            page_images = []

    pages: List[str] = []

    with pdfplumber.open(pdf_file) as pdf:

        for i, page in enumerate(pdf.pages):

            page_text = page.extract_text()

            if not page_text:
                page_text = _extract_text_from_words(page)

            # Try OCR for this page if images were loaded
            ocr_text = ""
            if page_images and i < len(page_images):
                ocr_text = _ocr_page(page_images[i])

            # Use OCR if available — it reads image-embedded text that pdfplumber misses
            if ocr_text.strip():
                best_text = ocr_text
            else:
                best_text = page_text or ""

            if not best_text:
                continue

            cleaned = _clean_page_text(best_text)

            pages.append(cleaned)

    return "\n".join(pages)


def extract_pages_from_pdf(pdf_path: str) -> List[str]:
    """
    Extract cleaned text page-by-page.
    """

    pdf_file = Path(pdf_path)

    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    pages_text: List[str] = []

    with pdfplumber.open(pdf_file) as pdf:

        for page in pdf.pages:

            page_text = page.extract_text()

            if not page_text:
                pages_text.append("")
                continue

            cleaned = _clean_page_text(page_text)

            pages_text.append(cleaned)

    return pages_text


def preview_pdf_text(pdf_path: str, max_chars: int = 1000) -> str:
    """
    Preview extracted text for debugging.
    """

    text = extract_text_from_pdf(pdf_path)

    return text[:max_chars]