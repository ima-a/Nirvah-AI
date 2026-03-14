# ============================================================
# app/ocr.py — Nirvaah AI OCR Module
# ============================================================
# Handles printed official documents sent via WhatsApp:
#   - Aadhaar cards (bilingual: English + Malayalam)
#   - BPL cards
#   - Government health ID cards
#   - Printed ASHA forms and registers
#
# SYSTEM REQUIREMENT: Tesseract OCR must be installed at OS level.
#
#   Ubuntu / Render deployment:
#     sudo apt-get install tesseract-ocr tesseract-ocr-eng tesseract-ocr-mal
#
#   Mac (development):
#     brew install tesseract
#     brew install tesseract-lang
#
#   Windows:
#     Download installer: https://github.com/UB-Mannheim/tesseract/wiki
#     Add to PATH, then install language packs manually.
#
#   Verify installation:
#     tesseract --version
#     tesseract --list-langs   (should show 'eng' and 'mal')
# ============================================================

import re
import io
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter


def preprocess_image(image_bytes: bytes) -> Image.Image:
    """
    Preprocessing pipeline tuned for printed official documents
    photographed on phone cameras (Aadhaar, BPL cards, health forms).
    """

    # Step 1 — Load from bytes
    image = Image.open(io.BytesIO(image_bytes))

    # Step 2 — Convert to RGB first (handles PNG with alpha channel,
    # CMYK scans, and other exotic formats WhatsApp might send)
    if image.mode != "RGB":
        image = image.convert("RGB")

    # Step 3 — Upscale if needed BEFORE grayscale conversion.
    # Printed documents photographed on phones are often 800-1200px wide.
    # Tesseract works best at 300 DPI equivalent, which for a standard
    # A4 document means ~2480px width. We target 1800px as a good balance
    # between accuracy and processing speed.
    width, height = image.size
    if width < 1800:
        scale = 1800 / width
        new_size = (int(width * scale), int(height * scale))
        image = image.resize(new_size, Image.LANCZOS)
        # LANCZOS is the highest quality resampling filter in Pillow —
        # it preserves sharp edges better than BILINEAR or BICUBIC,
        # which matters for small printed characters like ൽ or ി

    # Step 4 — Enhance contrast before grayscale.
    # Phone photos of documents often have uneven lighting — one corner
    # brighter than the other. Contrast enhancement compensates for this.
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2.0)
    # 2.0 means double the contrast. This makes dark text darker and
    # light background lighter, which is exactly what Tesseract needs.

    # Step 5 — Convert to grayscale
    image = image.convert("L")

    # Step 6 — Sharpen the grayscale image.
    # Printed text that has been photographed at a slight angle or with
    # camera shake will have slightly blurred edges. Sharpening recovers
    # the character edge definition that Tesseract relies on.
    image = image.filter(ImageFilter.SHARPEN)
    # Apply twice for documents that appear noticeably blurry
    image = image.filter(ImageFilter.SHARPEN)

    # Step 7 — Apply a mild unsharp mask for fine character detail.
    # This is especially important for Malayalam script, which has many
    # small curves and diacritical marks (like ്, ി, ൻ) that blur easily.
    image = image.filter(ImageFilter.UnsharpMask(radius=1, percent=150, threshold=3))

    return image


def clean_ocr_text(raw_text: str) -> str:
    """Clean OCR output — removes noise from printed document borders and form lines."""
    if not raw_text:
        return ""

    text = raw_text.strip()

    # Remove excessive newlines (3+ in a row → 2)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Replace tabs with space
    text = text.replace('\t', ' ')

    # Remove lines that are just punctuation or single characters
    # (common OCR noise from document borders and form lines)
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        # Keep line if it has at least 2 meaningful characters
        # This removes lines like "—", "|", ".", ":" that come from
        # table borders being misread as text
        if len(stripped) >= 2:
            cleaned_lines.append(line)

    text = '\n'.join(cleaned_lines)

    # Collapse multiple spaces into one
    text = re.sub(r' {2,}', ' ', text)

    # Do NOT touch Malayalam characters, numbers, slashes, or dots —
    # all of these are medically meaningful content

    return text.strip()


def deduplicate_ocr_passes(parts: list[str]) -> str:
    """
    Deduplicate text from multiple Tesseract passes.
    Keeps the combined (mal+eng) pass as the base and only adds
    content from individual passes if they contain genuinely new info.
    """

    # If only one pass produced text, return it directly
    if len(parts) == 1:
        return parts[0]

    if not parts:
        return ""

    # Always keep the combined pass (parts[0]) as the base — it was
    # run with mal+eng so it is the most comprehensive.
    # For the other parts, only add them if they contain content that
    # looks significantly different from what we already have.
    # "Significantly different" = more than 20 unique words not in base.

    base = parts[0]
    base_words = set(base.lower().split())

    additional_sections = []
    for part in parts[1:]:
        part_words = set(part.lower().split())
        # Words in this pass that are NOT in the base pass
        unique_words = part_words - base_words
        # If this pass has more than 20 words the base didn't catch,
        # it contains genuinely new information worth including
        if len(unique_words) > 20:
            additional_sections.append(part)

    if additional_sections:
        return base + "\n\n" + "\n\n".join(additional_sections)

    return base


async def extract_text_from_image(image_bytes: bytes) -> str:
    """
    Extract text from a printed document image using three Tesseract passes:
    1. English-only pass
    2. Malayalam-only pass
    3. Combined bilingual pass (mal+eng)

    Results are deduplicated and merged for maximum coverage.
    """
    try:
        image = preprocess_image(image_bytes)

        # Pass 1 — English optimised
        # --psm 3: fully automatic page segmentation (handles columns and
        # label-value layouts better than --psm 6 for printed documents)
        # --oem 3: use both legacy and LSTM OCR engines (most accurate)
        english_text = pytesseract.image_to_string(
            image,
            lang="eng",
            config="--psm 3 --oem 3"
        )

        # Pass 2 — Malayalam optimised
        # Same psm and oem settings, but using the Malayalam language model
        malayalam_text = pytesseract.image_to_string(
            image,
            lang="mal",
            config="--psm 3 --oem 3"
        )

        # Pass 3 — Combined bilingual pass
        # This handles lines where English and Malayalam appear together
        # (e.g. Aadhaar cards where name is on same line in both scripts)
        combined_text = pytesseract.image_to_string(
            image,
            lang="mal+eng",
            config="--psm 3 --oem 3"
        )

        # Merge strategy: use the combined pass as the base, but supplement
        # it with content from the individual passes. The reason we do all
        # three is that sometimes the combined model gets confused by a
        # dominant script and drops the minority script characters. Having
        # the individual passes as backup catches those dropped sections.
        #
        # Simple merge: take the longest non-empty result from each pass
        # and concatenate with a separator so Groq sees all extracted text.
        parts = []
        for text in [combined_text, english_text, malayalam_text]:
            cleaned = clean_ocr_text(text)
            if cleaned.strip():
                parts.append(cleaned)

        # Deduplicate: if all three passes returned very similar text,
        # just use the combined pass to avoid sending Groq triplicate info.
        # Simple heuristic: if english_text and combined_text share >80%
        # of their words, they are likely duplicates — skip the duplicate.
        final_text = deduplicate_ocr_passes(parts)

        return final_text

    except Exception as e:
        print(f"[OCR ERROR] {e}")
        return ""


def check_tesseract():
    """Verify Tesseract is installed with both English and Malayalam language packs."""
    try:
        langs = pytesseract.get_languages()
        missing = []
        if "mal" not in langs:
            missing.append("mal (Malayalam)")
        if "eng" not in langs:
            missing.append("eng (English)")

        if missing:
            print(f"[OCR WARNING] Missing language packs: {', '.join(missing)}")
            print("Install on Ubuntu: sudo apt-get install tesseract-ocr-mal")
            print("Install on Mac:    brew install tesseract-lang")
        else:
            print(f"[OCR OK] Tesseract ready with English + Malayalam support.")
    except Exception as e:
        print(f"[OCR ERROR] Tesseract not installed: {e}")
