# OCR Module

## File Map
- Implementation: [ocr.py](../nirvaah-backend/app/ocr.py)

## Purpose
Extracts text from printed official documents (Aadhaar cards, BPL cards, health ID cards, ASHA forms) photographed and sent via WhatsApp. Bilingual English + Malayalam support.

## System Requirement
Tesseract OCR must be installed at OS level:
```bash
# Ubuntu
sudo apt-get install tesseract-ocr tesseract-ocr-eng tesseract-ocr-mal

# Mac
brew install tesseract && brew install tesseract-lang
```

## Public API

### `preprocess_image(image_bytes: bytes) -> Image`
Phone-camera-optimized preprocessing pipeline:
1. Load from bytes → RGB conversion
2. Upscale to 1800px width (LANCZOS) if needed
3. Contrast enhancement (2.0×)
4. Grayscale conversion
5. Double sharpen + unsharp mask for Malayalam diacritical marks

### `extract_text_from_image(image_bytes: bytes) -> str`
Three Tesseract passes for maximum bilingual coverage:
1. **English-only** (`--psm 3 --oem 3`)
2. **Malayalam-only** (`--psm 3 --oem 3`)
3. **Combined** (`mal+eng --psm 3 --oem 3`)

Results are cleaned, deduplicated, and merged.

### `clean_ocr_text(raw_text: str) -> str`
Removes OCR noise: excessive newlines, single-char lines (table borders), collapsed spaces. Preserves Malayalam characters and medical values.

### `deduplicate_ocr_passes(parts: list[str]) -> str`
Keeps combined pass as base; only adds individual passes if they contain 20+ unique words not in the base.

### `check_tesseract()`
Verifies Tesseract installation and `eng` + `mal` language packs.

## Python Dependencies
`pytesseract`, `Pillow`
