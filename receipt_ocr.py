# receipt_ocr.py
"""
Receipt scanner with AI vision analysis.

AI extraction priority (uses whichever key is provided):
  1. Claude (Anthropic)   — best at structured JSON, understands Swedish natively
  2. GPT-4o (OpenAI)      — excellent vision + Swedish support
  3. Gemini (Google)      — good quality, generous free tier

Fallback (no AI key):
  4. Tesseract OCR + MyMemory translation (original behaviour)

Dependencies:
    pip install anthropic openai pillow requests streamlit
    # For fallback OCR only:
    pip install pytesseract
    sudo apt-get install tesseract-ocr tesseract-ocr-swe
"""

import re
import io
import json
import os
import base64
import logging
import requests
import streamlit as st
import pandas as pd
from datetime import date
from typing import Optional, Dict, List, Tuple

from config import CLAUDE_MODEL
from security_utils import validate_upload, UploadValidationError

log = logging.getLogger("receipt_ocr")


# ═══════════════════════════════════════════════════════════════
# AI VISION EXTRACTION
# ═══════════════════════════════════════════════════════════════

# Prompt sent to every AI model — returns structured JSON directly.
def _build_system_prompt(dropdown_options: Dict) -> str:
    """
    Build the AI system prompt, injecting category/subcategory options
    from dropdown_options.json so the AI picks from your exact taxonomy.
    """
    if dropdown_options:
        # Build a compact category → [subcategories] reference for the prompt
        cat_lines = []
        for cat, subs in sorted(dropdown_options.items()):
            if isinstance(subs, list):
                sub_list = ", ".join(sorted(subs))
            elif isinstance(subs, dict):
                sub_list = ", ".join(sorted(subs.keys()))
            else:
                sub_list = "General"
            cat_lines.append(f"  - {cat}: [{sub_list}]")
        taxonomy_block = (
            "- You MUST use ONLY the following categories and subcategories. "
            "Pick the closest match for each item:\n"
            + "\n".join(cat_lines)
        )
    else:
        taxonomy_block = (
            "- Use your knowledge to assign sensible category and subcategory values.\n"
            "  Example categories: Groceries, Household, Personal Care, Beverages, Bakery, Dairy, Meat & Fish"
        )

    return f"""You are a receipt data extraction assistant.
The user will send you a photo of a receipt (possibly in Swedish or another language).
Extract all information and return ONLY valid JSON — no markdown, no explanation, no extra text.

Return this exact structure:
{{"shop":"store name or Unknown","date":"YYYY-MM-DD or null","total":0.00,"currency":"SEK","items":[{{"name":"item name in English","price":0.00,"quantity":1.0,"quantity_unit":"pcs","category":"category","subcategory":"subcategory"}}]}}

Rules:
- Return ONLY the JSON object. No markdown, no code fences, no explanation.
- Translate all item names to English.
- Skip metadata lines: VAT, deposits (+PANT), loyalty savings, reference numbers, terminal IDs.
- quantity_unit must be one of: pcs, kg, g, l, ml
{taxonomy_block}
- ALL numeric fields MUST be valid JSON numbers (e.g. 0.0, 12.50, 1.0). NEVER write a bare dot (.) or leave a value empty.
- If a price is unreadable, use 0.0. If quantity is unknown, use 1.0.
- NEVER use trailing commas. Every JSON array and object must be properly closed.
- Negative prices (discounts/returns) are allowed but must be valid numbers like -8.88.
- Return COMPACT JSON with no indentation or extra whitespace to keep the response short.
"""

_USER_PROMPT = "Please extract all receipt data from this image and return as JSON."


# ═══════════════════════════════════════════════════════════════
# PDF → IMAGE CONVERSION
# ═══════════════════════════════════════════════════════════════

def pdf_to_images(pdf_bytes: bytes) -> List[bytes]:
    """
    Convert every page of a PDF to a JPEG image (bytes).

    Tries pymupdf (fitz) first — no system dependency needed.
    Falls back to pdf2image which requires poppler:
        sudo apt-get install poppler-utils   (Linux)
        brew install poppler                 (macOS)
    """
    # ── pymupdf (preferred) ────────────────────────────────────
    try:
        import fitz  # pymupdf

        doc    = fitz.open(stream=pdf_bytes, filetype="pdf")
        images = []
        for page in doc:
            # Render at 2× zoom for sharper text — receipts are usually narrow
            mat    = fitz.Matrix(2.0, 2.0)
            pix    = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
            images.append(pix.tobytes("jpeg"))
        doc.close()
        return images

    except ImportError:
        log.debug("pymupdf (fitz) not available, falling back to pdf2image")

    # ── pdf2image (fallback) ───────────────────────────────────
    try:
        from pdf2image import convert_from_bytes
        from PIL import Image

        pages  = convert_from_bytes(pdf_bytes, dpi=200)
        images = []
        for page in pages:
            buf = io.BytesIO()
            page.convert("RGB").save(buf, format="JPEG", quality=90)
            images.append(buf.getvalue())
        return images

    except ImportError:
        raise ImportError(
            "No PDF library found. Install one:\n"
            "  pip install pymupdf          (recommended — no system deps)\n"
            "  pip install pdf2image        (also needs: sudo apt install poppler-utils)"
        )


def merge_parsed_pages(pages: List[Dict]) -> Dict:
    """
    Merge extraction results from multiple PDF pages into one receipt.
    Uses the date/shop/total from the first non-empty page; combines all items.
    """
    merged = {"date": None, "shop": "Unknown", "total": 0.0, "currency": "SEK", "items": []}
    for page in pages:
        if not merged["date"] and page.get("date"):
            merged["date"] = page["date"]
        if merged["shop"] == "Unknown" and page.get("shop") not in (None, "", "Unknown"):
            merged["shop"] = page["shop"]
        if not merged["total"] and page.get("total"):
            merged["total"] = page["total"]
        if page.get("currency"):
            merged["currency"] = page["currency"]
        merged["items"].extend(page.get("items", []))
    return merged


def _friendly_error(provider: str, e: Exception) -> str:
    """Turn raw API errors into actionable messages."""
    msg = str(e)
    if "insufficient_quota" in msg or "429" in msg:
        links = {
            "Claude":  "https://console.anthropic.com/settings/billing",
            "GPT-4o":  "https://platform.openai.com/settings/billing",
            "Gemini":  "https://aistudio.google.com/app/apikey",
        }
        link = links.get(provider, "your provider's billing page")
        return (
            f"**{provider} quota exceeded.** Your free credit has run out.\n\n"
            f"To fix: add a payment method at {link} (a small top-up lasts many months).\n"
            f"Or switch to **Gemini** — it has a free tier with 1,500 requests/day, no card needed."
        )
    if "timed out" in msg.lower() or "timeout" in msg.lower():
        return (
            f"**{provider} timed out.** The image may be too large or the connection too slow. "
            "The app automatically compresses images — if this keeps happening, "
            "try a lower-resolution photo."
        )
    if "invalid_api_key" in msg or "401" in msg or "403" in msg:
        return f"**{provider} API key is invalid or revoked.** Please regenerate it."
    if "No module named" in msg:
        pkg = "openai" if provider == "GPT-4o" else "anthropic"
        return f"**{provider} SDK not installed.** Run: `pip install {pkg}`"
    return f"**{provider} error:** {msg}"


def _compress_image(image_bytes: bytes, max_kb: int = 800, max_dimension: int = 1600) -> bytes:
    """
    Shrink an image to at most max_kb kilobytes and max_dimension pixels on the longest side.
    Keeps aspect ratio. Returns JPEG bytes.
    Smaller images = faster API calls and fewer timeouts.
    """
    from PIL import Image

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    # Resize if too large
    w, h = img.size
    longest = max(w, h)
    if longest > max_dimension:
        scale  = max_dimension / longest
        img    = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    # Compress to target size
    quality = 85
    while quality >= 40:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        if buf.tell() <= max_kb * 1024:
            break
        quality -= 10

    return buf.getvalue()


def extract_with_ai(
    image_bytes: bytes,
    anthropic_key:    Optional[str] = None,
    openai_key:       Optional[str] = None,
    gemini_key:       Optional[str] = None,
    dropdown_options: Dict          = None,
) -> Tuple[Dict, str]:
    """
    Send the receipt image to an AI vision model and get structured data back.
    Tries providers in order: Claude → GPT-4o → Gemini.
    Passes dropdown_options into the prompt so the AI uses your exact taxonomy.

    Returns:
        (parsed_dict, provider_name)
    """
    # Compress image before sending — reduces upload time and avoids timeouts
    try:
        image_bytes = _compress_image(image_bytes)
    except Exception as e:
        log.warning("Image compression failed, sending original: %s", e)

    system_prompt = _build_system_prompt(dropdown_options or {})
    failures = []

    if anthropic_key:
        try:
            data = _extract_claude(image_bytes, anthropic_key, system_prompt)
            return data, "Claude (Anthropic)"
        except Exception as e:
            msg = _friendly_error("Claude", e)
            st.warning(msg)
            failures.append(("Claude", msg))

    if openai_key:
        try:
            data = _extract_gpt4o(image_bytes, openai_key, system_prompt)
            return data, "GPT-4o (OpenAI)"
        except Exception as e:
            msg = _friendly_error("GPT-4o", e)
            st.warning(msg)
            failures.append(("GPT-4o", msg))

    if gemini_key:
        try:
            data = _extract_gemini(image_bytes, gemini_key, system_prompt)
            return data, "Gemini (Google)"
        except Exception as e:
            msg = _friendly_error("Gemini", e)
            st.warning(msg)
            failures.append(("Gemini", msg))

    if failures:
        # Show a clear summary of what failed and why
        st.error(
            "All AI providers failed. Reasons:\n"
            + "\n".join(f"- **{name}**: {reason}" for name, reason in failures)
        )
    return {}, ""


def _extract_claude(image_bytes: bytes, api_key: str, system_prompt: str = None) -> Dict:
    """Claude claude-sonnet-4-20250514 via Anthropic API."""
    system_prompt = system_prompt or _build_system_prompt({})
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    encoded = base64.standard_b64encode(image_bytes).decode("utf-8")

    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=8192,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": encoded,
                        },
                    },
                    {"type": "text", "text": _USER_PROMPT},
                ],
            }
        ],
    )
    raw = message.content[0].text.strip()
    return _safe_parse_json(raw)


def _extract_gpt4o(image_bytes: bytes, api_key: str, system_prompt: str = None) -> Dict:
    """GPT-4o via OpenAI API."""
    system_prompt = system_prompt or _build_system_prompt({})
    try:
        import openai
    except ImportError:
        raise ImportError(
            "openai package not installed.\n"
            "Run: pip install openai\n"
            "Or add 'openai' to your requirements.txt and redeploy."
        )

    client  = openai.OpenAI(api_key=api_key)
    encoded = base64.b64encode(image_bytes).decode("utf-8")

    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=8192,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
                    },
                    {"type": "text", "text": _USER_PROMPT},
                ],
            },
        ],
    )
    raw = response.choices[0].message.content.strip()
    return _safe_parse_json(raw)


def _validate_gemini_key(api_key: str) -> Tuple[bool, List[str], str]:
    """
    Call the Gemini models-list endpoint to validate the key and discover
    which vision-capable models are actually available.

    Returns:
        (key_is_valid, list_of_available_vision_models, error_message)
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        resp = requests.get(url, timeout=10)
    except requests.RequestException as e:
        return False, [], f"Network error: {e}"

    if resp.status_code == 400:
        return False, [], "API key is invalid or malformed (400). Regenerate it at https://aistudio.google.com/app/apikey"
    if resp.status_code == 403:
        return False, [], "API key is valid but access is denied (403). Make sure the Generative Language API is enabled in your Google Cloud project."
    if resp.status_code == 401:
        return False, [], "API key rejected (401). It may have been revoked. Regenerate at https://aistudio.google.com/app/apikey"
    if not resp.ok:
        return False, [], f"Unexpected error {resp.status_code}: {resp.text[:200]}"

    # Key is valid — filter to models that support generateContent and have vision
    all_models = resp.json().get("models", [])
    vision_models = [
        m["name"].replace("models/", "")
        for m in all_models
        if "generateContent" in m.get("supportedGenerationMethods", [])
        and "vision" in m.get("description", "").lower()
        or "flash" in m.get("name", "").lower()
        or "pro" in m.get("name", "").lower()
    ]
    return True, vision_models, ""


def _extract_gemini(image_bytes: bytes, api_key: str, system_prompt: str = None) -> Dict:
    """
    Gemini via Google Generative AI REST API.
    Validates the key first, then discovers available models dynamically
    so it works regardless of which models Google currently offers.
    """
    # Step 1: validate key and discover available models
    key_valid, discovered_models, key_error = _validate_gemini_key(api_key)

    if not key_valid:
        raise RuntimeError(key_error)

    # Step 2: build candidate list — discovered models first, known names as fallback
    known_models = [
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-2.5-flash",
        "gemini-1.5-flash-latest",
        "gemini-1.5-flash",
        "gemini-1.5-pro-latest",
        "gemini-1.5-pro",
    ]
    # Deduplicate while keeping discovered ones first
    seen = set()
    candidates = []
    for m in (discovered_models + known_models):
        if m not in seen:
            candidates.append(m)
            seen.add(m)

    # Step 3: build the request payload
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt or _build_system_prompt({})}]},
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": "image/jpeg", "data": encoded}},
                {"text": _USER_PROMPT},
            ]
        }],
        "generationConfig": {"maxOutputTokens": 8192},
    }

    # Step 4: try each candidate
    tried = []
    for model in candidates:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={api_key}"
        )
        try:
            resp = requests.post(url, json=payload, timeout=120)
            if resp.status_code == 404:
                tried.append(f"{model} → 404 not found")
                continue
            if resp.status_code == 400:
                # 400 on a specific model usually means unsupported feature (e.g. no vision)
                tried.append(f"{model} → 400 unsupported")
                continue
            resp.raise_for_status()
            raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            return _safe_parse_json(raw)
        except (requests.HTTPError, KeyError, IndexError) as e:
            tried.append(f"{model} → {e}")
            continue

    raise RuntimeError(
        f"Key is valid but no working Gemini model found.\n"
        f"Tried: {', '.join(tried) or 'none'}\n"
        f"Available from API: {', '.join(discovered_models) or 'none returned'}"
    )


def _fix_common_json_errors(s: str) -> str:
    """Fix common Gemini JSON formatting quirks."""
    # Fix bare dot: ": ."  or  ": -."  before delimiter
    s = re.sub(r':\s*(-?)\.\s*(?=[,\}\]\n])', r': \g<1>0.0', s)
    s = re.sub(r':\s*(-?)\.$', r': \g<1>0.0', s)
    # Fix number followed by loose dot: -8.88,. → -8.88
    s = re.sub(r'(:\s*-?\d+\.?\d*),\.', r'', s)
    # Fix trailing dot after number before delimiter: 8., → 8.0,
    s = re.sub(r'(\d)\.\s*([,\}\]])', r'\g<1>.0\2', s)
    # Fix trailing commas before } or ]
    s = re.sub(r',\s*([\}\]])', r'\1', s)
    return s


def _close_json(s: str) -> str:
    """
    Attempt to close a truncated JSON string.
    If truncated inside a string value, close the string first,
    then close any open brackets/braces.
    """
    stack     = []
    in_string = False
    escape    = False

    for ch in s:
        if escape:
            escape = False
            continue
        if ch == '\\':
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if not in_string:
            if ch in ('{', '['):
                stack.append('}' if ch == '{' else ']')
            elif ch in ('}', ']') and stack:
                stack.pop()

    suffix = ''
    if in_string:
        suffix += '"'          # close the open string
    suffix += ''.join(reversed(stack))
    return s + suffix


def _strip_incomplete_items(data: Dict) -> Dict:
    """
    Remove the last item in the items list if it looks incomplete
    (missing required fields like price or name).
    Shows a warning so the user knows to check.
    """
    items = data.get('items', [])
    if not items:
        return data

    last = items[-1]
    required = ('name', 'price', 'quantity', 'quantity_unit', 'category', 'subcategory')
    if not all(k in last for k in required):
        items = items[:-1]
        data['items'] = items
        st.warning(
            f"The receipt was too long for one response — the last item was cut off and removed. "
            f"{len(items)} items were recovered. Check the list below and add any missing items manually."
        )
    return data


def _safe_parse_json(raw: str) -> Dict:
    """
    Robustly parse JSON from an AI response.
    Handles:
      - Markdown code fences
      - Bare dot values        ("price": .)
      - Trailing commas        (1.0,} or [1,])
      - Truncation mid-value   ("cat  →  recovers all complete items)
      - Truncation mid-string  ("categ  →  closes string, closes brackets)
    """
    # Strip markdown fences
    cleaned = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw, flags=re.DOTALL).strip()

    cleaned = _fix_common_json_errors(cleaned)

    # Attempt 1: parse cleaned as-is
    try:
        return _strip_incomplete_items(json.loads(cleaned))
    except json.JSONDecodeError:
        pass

    # Attempt 2: extract outermost JSON object (strips surrounding noise)
    m = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if m:
        try:
            return _strip_incomplete_items(json.loads(m.group()))
        except json.JSONDecodeError:
            pass

    # Attempt 3: close unclosed brackets / strings
    closed = _close_json(cleaned)
    closed = _fix_common_json_errors(closed)  # re-run fixes after closing
    try:
        return _strip_incomplete_items(json.loads(closed))
    except json.JSONDecodeError:
        pass

    # Attempt 4: extract only fully-formed item objects, discard the incomplete trailing one
    header_m = re.match(r'(\{.*?"items"\s*:\s*\[)', cleaned, re.DOTALL)
    if header_m:
        items_section  = cleaned[len(header_m.group(1)):]
        complete_items = re.findall(r'\{[^{}]*\}', items_section, re.DOTALL)
        if complete_items:
            rebuilt  = header_m.group(1) + ','.join(complete_items) + ']}'
            rebuilt  = _fix_common_json_errors(rebuilt)
            try:
                result = json.loads(rebuilt)
                st.warning(
                    f"The receipt had too many items for one response — "
                    f"{len(result.get('items',[]))} items were recovered. "
                    f"The last item was cut off; add it manually if needed."
                )
                return result
            except json.JSONDecodeError:
                pass

    raise ValueError(f"AI returned invalid JSON: Could not recover.\n\nRaw response:\n{raw[:600]}")


# ═══════════════════════════════════════════════════════════════
# FALLBACK: OCR + TRANSLATION (no AI key)
# ═══════════════════════════════════════════════════════════════

def extract_text_from_image(
    uploaded_file,
    google_vision_key: Optional[str] = None,
) -> Tuple[str, float]:
    if uploaded_file is None:
        return "", 0.0
    uploaded_file.seek(0)
    image_bytes = uploaded_file.read()
    if google_vision_key:
        try:
            return _extract_with_google_vision(image_bytes, google_vision_key)
        except Exception as e:
            st.warning(f"Google Vision failed: {e}. Falling back to Tesseract…")
    try:
        return _extract_with_tesseract(image_bytes)
    except ImportError:
        st.error("pytesseract not installed. Run: pip install pytesseract pillow")
        return "", 0.0
    except Exception as e:
        st.error(f"OCR failed: {e}")
        return "", 0.0


def _extract_with_google_vision(image_bytes: bytes, api_key: str) -> Tuple[str, float]:
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    url = f"https://vision.googleapis.com/v1/images:annotate?key={api_key}"
    payload = {"requests": [{"image": {"content": encoded}, "features": [{"type": "TEXT_DETECTION"}]}]}
    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()
    annotation = resp.json().get("responses", [{}])[0].get("fullTextAnnotation", {})
    return annotation.get("text", ""), -1.0


def _extract_with_tesseract(image_bytes: bytes) -> Tuple[str, float]:
    import pytesseract
    from PIL import Image
    image = Image.open(io.BytesIO(image_bytes)).convert("L")
    try:
        text = pytesseract.image_to_string(image, lang="swe+eng")
    except pytesseract.TesseractError:
        text = pytesseract.image_to_string(image, lang="eng")
    return text.strip(), -1.0


def translate_swedish_to_english(
    text: str,
    google_key: Optional[str] = None,
    deepl_key:  Optional[str] = None,
) -> Tuple[str, str]:
    if not text:
        return text, "none"
    if google_key:
        try:
            return _translate_google(text, google_key), "Google Translate"
        except Exception:
            pass
    if deepl_key:
        try:
            return _translate_deepl(text, deepl_key), "DeepL"
        except Exception:
            pass
    try:
        return _translate_mymemory(text), "MyMemory (free)"
    except Exception:
        return text, "none"


def _translate_google(text: str, api_key: str) -> str:
    parts = []
    for chunk in _chunk_text(text, 4800):
        resp = requests.post(
            "https://translation.googleapis.com/language/translate/v2",
            params={"key": api_key},
            json={"q": chunk, "source": "sv", "target": "en", "format": "text"},
            timeout=10,
        )
        resp.raise_for_status()
        parts.append(resp.json()["data"]["translations"][0]["translatedText"])
    return "\n".join(parts)


def _translate_deepl(text: str, api_key: str) -> str:
    base = "https://api-free.deepl.com" if api_key.endswith(":fx") else "https://api.deepl.com"
    parts = []
    for chunk in _chunk_text(text, 4800):
        resp = requests.post(
            f"{base}/v2/translate",
            headers={"Authorization": f"DeepL-Auth-Key {api_key}"},
            data={"text": chunk, "source_lang": "SV", "target_lang": "EN"},
            timeout=10,
        )
        resp.raise_for_status()
        parts.append(resp.json()["translations"][0]["text"])
    return "\n".join(parts)


def _translate_mymemory(text: str) -> str:
    parts = []
    for chunk in _chunk_text(text, 450):
        resp = requests.get(
            "https://api.mymemory.translated.net/get",
            params={"q": chunk, "langpair": "sv|en"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        parts.append(
            data["responseData"]["translatedText"]
            if data.get("responseStatus") == 200
            else chunk
        )
    return "\n".join(parts)


def _chunk_text(text: str, max_chars: int) -> List[str]:
    lines, chunks, current = text.splitlines(keepends=True), [], ""
    for line in lines:
        if len(current) + len(line) > max_chars:
            if current:
                chunks.append(current)
            current = line
        else:
            current += line
    if current:
        chunks.append(current)
    return chunks or [text]


def parse_receipt_text(text: str) -> Dict:
    if not text:
        return {"error": "empty", "items": []}
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return {
        "date":  _parse_date(lines),
        "shop":  _parse_shop(lines),
        "total": _parse_total(lines),
        "items": _parse_items(lines),
    }


_DATE_PATS = [
    (r"\b(\d{4})[-/](\d{2})[-/](\d{2})\b", "ymd"),
    (r"\b(\d{2})[-/](\d{2})[-/](\d{4})\b", "dmy"),
    (r"\b(\d{1,2})\s+(jan|feb|mar|apr|maj|jun|jul|aug|sep|okt|nov|dec)\w*\s+(\d{4})\b", "sv"),
]
_SV_MON = {"jan":1,"feb":2,"mar":3,"apr":4,"maj":5,"jun":6,"jul":7,"aug":8,"sep":9,"okt":10,"nov":11,"dec":12}

def _parse_date(lines):
    full = " ".join(lines)
    for pat, fmt in _DATE_PATS:
        m = re.search(pat, full, re.IGNORECASE)
        if not m:
            continue
        try:
            if fmt == "ymd": return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if fmt == "dmy": return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            if fmt == "sv":  return date(int(m.group(3)), _SV_MON.get(m.group(2)[:3].lower(), 1), int(m.group(1)))
        except ValueError:
            continue
    return date.today()


_SHOPS = ["willys","ica","coop","lidl","hemköp","hemkop","netto","citygross","maxi","tempo","mathem"]

def _parse_shop(lines):
    for line in lines[:8]:
        if any(s in line.lower() for s in _SHOPS):
            return line.strip()
    for line in lines[:5]:
        if line and not re.match(r'^[\d\s.,:/-]+$', line):
            return line.strip()
    return "Unknown"

def _parse_total(lines):
    for line in lines:
        if re.search(r"totalt?|summa|att\s+betala|belopp|mott", line, re.IGNORECASE):
            amounts = re.findall(r"\d+[.,]\d{2}", line)
            if amounts:
                return _to_float(amounts[-1])
    all_a = [_to_float(m) for l in lines for m in re.findall(r"\b\d+[.,]\d{2}\b", l)]
    return max(all_a) if all_a else 0.0

_SKIP = re.compile(
    r"^\s*$|kvitto|org\.?\s*nr|moms|totalt?|summa|att\s+betala|belopp|mott"
    r"|\+pant|willys\s+plus|sparat|plus-nummer|ref(erence)?[\s:]|term(inal)?[\s:]"
    r"|datum|butik|kassör|^tfn[:\s]|^\d{3,}-\d{3,}|0[,\.]\d{3}kr|kr/ksa|kr/st|^[0-9,. ]+$",
    re.IGNORECASE,
)
_ITEM_RE = re.compile(r"^(.+?)\s{2,}(\d+[.,]\d{2})\s*$|^(.+?)\s+(\d+[.,]\d{2})\s*$")
_QTY_RE  = re.compile(r"^(\d+[.,]?\d*)\s*(?:x|st|kg\*?|l\*?|liter)\s+(.+)", re.IGNORECASE)

def _parse_items(lines):
    items = []
    for line in lines:
        if _SKIP.search(line): continue
        m = _ITEM_RE.match(line)
        if not m: continue
        name_raw  = (m.group(1) or m.group(3) or "").strip()
        price     = _to_float((m.group(2) or m.group(4) or "0").strip())
        if price <= 0: continue
        qty = 1.0
        qm  = _QTY_RE.match(name_raw)
        if qm:
            qty      = _to_float(qm.group(1))
            name_raw = qm.group(2).strip()
        name = re.sub(r"\s{2,}|[|\\]", " ", name_raw).strip()
        if len(name) >= 2:
            items.append({"name": name, "price": price, "quantity": qty,
                          "quantity_unit": "pcs", "category": "Groceries", "subcategory": "General"})
    return items

def _to_float(s):
    try: return float(str(s).replace(",", "."))
    except (ValueError, TypeError): return 0.0


# ═══════════════════════════════════════════════════════════════
# DROPDOWN HELPERS
# ═══════════════════════════════════════════════════════════════

def _load_dropdown_options() -> Dict:
    try:
        path = os.path.join("data", "dropdown_options.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _get_categories(options: Dict) -> List[str]:
    if isinstance(options, dict) and options:
        return sorted(options.keys())
    return [
        "Groceries","Dairy","Bakery","Meat & Fish","Beverages","Household",
        "Personal Care","Electronics","Clothing","Dining Out","Transport",
        "Health","Entertainment","Sports & Fitness","Other",
    ]

def _get_subcategories(options: Dict, category: str) -> List[str]:
    if isinstance(options, dict) and category in options:
        subs = options[category]
        return sorted(subs if isinstance(subs, list) else subs.keys())
    return ["General"]


# ═══════════════════════════════════════════════════════════════
# MAIN UI
# ═══════════════════════════════════════════════════════════════

def receipt_upload_ui_with_translation(df, save_fn, sheet=None):
    from config import Columns, QuantityUnit

    st.title("📷 Receipt Scanner")
    st.markdown(
        "A 3-stage pipeline: **upload** receipts, **translate & edit** them, "
        "then **push** to the expense table. Receipts are saved to Google Drive "
        "at every stage, so you can resume any time."
    )

    dropdown_options = _load_dropdown_options()
    all_categories   = _get_categories(dropdown_options)
    all_units        = QuantityUnit.all()

    # ── Load keys: secrets first, UI inputs as override ────────
    def _secret(key: str) -> str:
        """Read from st.secrets if present, else return empty string."""
        try:
            return st.secrets.get(key, "")
        except Exception:
            return ""

    # Keys from secrets.toml / Streamlit Cloud secrets (persistent)
    s_anthropic  = _secret("ANTHROPIC_API_KEY")
    s_openai     = _secret("OPENAI_API_KEY")
    s_gemini     = _secret("GEMINI_API_KEY")
    s_vision     = _secret("GOOGLE_VISION_KEY")
    s_google_tr  = _secret("GOOGLE_TRANSLATE_KEY")
    s_deepl      = _secret("DEEPL_API_KEY")

    keys_from_secrets = any([s_anthropic, s_openai, s_gemini])

    with st.expander(
        "🤖 AI & API Configuration"
        + (" ✅ *(keys loaded from secrets)*" if keys_from_secrets else ""),
        expanded=not keys_from_secrets,   # auto-close if secrets are already set
    ):
        if keys_from_secrets:
            st.success(
                "API keys are loaded from **Streamlit secrets** — no need to enter them here. "
                "You can still paste a key below to temporarily override a secret."
            )
        else:
            st.markdown(
                "**Option A — set once, works forever (recommended):**  \n"
                "Add your keys to `.streamlit/secrets.toml` (local) or the "
                "**Streamlit Cloud → Settings → Secrets** panel (hosted). "
                "The app will pick them up automatically on every load.\n\n"
                "```toml\n"
                "# .streamlit/secrets.toml\n"
                "ANTHROPIC_API_KEY    = \"sk-ant-...\"\n"
                "OPENAI_API_KEY       = \"sk-...\"\n"
                "GEMINI_API_KEY       = \"AIza...\"\n"
                "GOOGLE_VISION_KEY    = \"AIza...\"\n"
                "GOOGLE_TRANSLATE_KEY = \"AIza...\"\n"
                "DEEPL_API_KEY        = \"...\"\n"
                "```\n\n"
                "**Option B — enter below** *(cleared on every browser refresh)*:"
            )

        st.markdown("##### 🤖 AI Vision Keys")
        col1, col2, col3 = st.columns(3)
        with col1:
            ui_anthropic = st.text_input("Claude (Anthropic)", type="password",
                                         placeholder="From secrets" if s_anthropic else "sk-ant-...",
                                         help="console.anthropic.com")
        with col2:
            ui_openai    = st.text_input("GPT-4o (OpenAI)",    type="password",
                                         placeholder="From secrets" if s_openai else "sk-...",
                                         help="platform.openai.com")
        with col3:
            ui_gemini    = st.text_input("Gemini (Google)",    type="password",
                                         placeholder="From secrets" if s_gemini else "AIza...",
                                         help="aistudio.google.com — free tier, 1500 req/day")

        st.markdown("##### 🔡 Fallback OCR & Translation Keys")
        col4, col5, col6 = st.columns(3)
        with col4:
            ui_vision    = st.text_input("Google Vision",      type="password",
                                         placeholder="From secrets" if s_vision else "")
        with col5:
            ui_google_tr = st.text_input("Google Translate",   type="password",
                                         placeholder="From secrets" if s_google_tr else "")
        with col6:
            ui_deepl     = st.text_input("DeepL",              type="password",
                                         placeholder="From secrets" if s_deepl else "")

    # UI input overrides secret when both are present
    anthropic_key = ui_anthropic  or s_anthropic
    openai_key    = ui_openai     or s_openai
    gemini_key    = ui_gemini     or s_gemini
    vision_key    = ui_vision     or s_vision
    google_tr_key = ui_google_tr  or s_google_tr
    deepl_key     = ui_deepl      or s_deepl

    has_ai = any([anthropic_key, openai_key, gemini_key])

    if has_ai:
        source = "secrets" if keys_from_secrets and not any([ui_anthropic, ui_openai, ui_gemini]) else "provided key"
        st.info(f"🤖 AI mode active ({source}) — the model will read, translate, and categorise the receipt directly.")

        # Gemini key health check (only when Gemini is the sole AI key)
        if gemini_key and not anthropic_key and not openai_key:
            with st.spinner("Validating Gemini API key..."):
                key_ok, avail_models, key_err = _validate_gemini_key(gemini_key)
            if not key_ok:
                msg = (
                    "Gemini key problem: " + key_err + "\n\n"
                    "Steps to fix:\n"
                    "1. Go to https://aistudio.google.com/app/apikey\n"
                    "2. Click Create API key and choose any Google Cloud project\n"
                    "3. Copy the key — it should start with AIza and be ~39 characters\n"
                    "4. Paste it into the field above or into secrets.toml"
                )
                st.error(msg)
                return
            elif avail_models:
                st.success("Gemini key valid. Will use: " + avail_models[0])
    else:
        st.info("📝 Fallback mode — using OCR + MyMemory translation (free). Add an AI key above for better results.")

    # ── 3-stage pipeline ───────────────────────────────────────
    # Stage 1 Upload → Stage 2 Translate & edit → Stage 3 Archive.
    # A receipt physically moves between folders (local + Drive) as it
    # progresses, so work can be resumed after a crash/restart.
    import scanner_store as ss

    # Recover any in-flight receipts from Drive (best-effort, once/session).
    ss.sync_from_drive()

    keys = {
        "anthropic": anthropic_key, "openai": openai_key, "gemini": gemini_key,
        "vision": vision_key, "google_tr": google_tr_key, "deepl": deepl_key,
    }

    tab_upload, tab_translate, tab_archive = st.tabs(
        ["1️⃣ Upload", "2️⃣ Translate & Push", "3️⃣ Archive"]
    )

    with tab_upload:
        _stage1_upload_ui(ss)

    with tab_translate:
        _stage2_translate_ui(
            ss, df, save_fn, sheet, keys, has_ai,
            dropdown_options, all_categories, all_units,
        )

    with tab_archive:
        _stage3_archive_ui(ss)


# ═══════════════════════════════════════════════════════════════
# 3-STAGE PIPELINE HELPERS
# ═══════════════════════════════════════════════════════════════
def _preview_receipt(ss, stage, receipt_id, filename, width=160):
    """Show an inline thumbnail (image) or a filename caption (PDF/other)."""
    if ss.is_image(filename):
        data = ss.read_receipt_bytes(stage, receipt_id)
        if data:
            st.image(data, width=width)
            return
    st.caption(f"📄 {filename}")


def _run_extraction(file_bytes, original_name, keys, has_ai, dropdown_options):
    """Run AI (or OCR fallback) extraction on a receipt's bytes."""
    is_pdf = (original_name or "").lower().endswith(".pdf")
    if is_pdf:
        try:
            page_images = pdf_to_images(file_bytes)
        except ImportError as e:
            st.error(str(e))
            return {}, ""
        except Exception as e:  # noqa: BLE001
            st.error(f"PDF conversion failed: {e}")
            return {}, ""
    else:
        page_images = [file_bytes]

    if has_ai:
        results = []
        provider = ""
        for i, img in enumerate(page_images):
            label = f"page {i+1}/{len(page_images)}" if len(page_images) > 1 else "receipt"
            with st.spinner(f"🤖 AI reading {label}…"):
                r, provider = extract_with_ai(
                    img,
                    anthropic_key=keys["anthropic"] or None,
                    openai_key=keys["openai"] or None,
                    gemini_key=keys["gemini"] or None,
                    dropdown_options=dropdown_options,
                )
            if r:
                results.append(r)
        return (merge_parsed_pages(results) if results else {}), provider

    # OCR fallback
    texts = []
    for i, img in enumerate(page_images):
        label = f"page {i+1}/{len(page_images)}" if len(page_images) > 1 else "receipt"
        with st.spinner(f"📷 OCR on {label}…"):
            img_file = io.BytesIO(img)
            img_file.name = "page.jpg"
            text, _ = extract_text_from_image(img_file, keys["vision"] or None)
        if text:
            texts.append(text)
    raw_sv = "\n".join(texts)
    if not raw_sv:
        return {}, ""
    with st.spinner("🌐 Translating…"):
        raw_en, provider = translate_swedish_to_english(
            raw_sv,
            google_key=keys["google_tr"] or None,
            deepl_key=keys["deepl"] or None,
        )
    with st.spinner("🔎 Parsing…"):
        parsed = parse_receipt_text(raw_en)
    return parsed, provider


def _stage1_upload_ui(ss):
    """Stage 1 — upload receipts into the translation queue."""
    st.markdown("#### Upload receipts for translation")
    st.caption(
        "Files are saved to the **Uploads** folder (local + Google Drive). "
        "If the app closes, your queue is preserved here."
    )

    uploads = st.file_uploader(
        "Upload receipt(s) — image or PDF",
        type=["jpg", "jpeg", "png", "webp", "pdf"],
        accept_multiple_files=True,
        key="scanner_uploader",
    )
    if uploads and st.button("⬆️ Save to queue", type="primary", key="scanner_save"):
        saved = 0
        for uf in uploads:
            try:
                # Cap receipt size to guard against memory-exhaustion /
                # decompression-bomb inputs before decoding.
                validate_upload(uf, max_mb=15)
                uf.seek(0)
                ss.save_upload(uf.read(), uf.name, uf.type)
                saved += 1
            except UploadValidationError as e:
                st.error(f"Skipped {uf.name}: {e}")
            except Exception as e:  # noqa: BLE001
                st.error(f"Failed to save {uf.name}: {e}")
        if saved:
            st.success(f"✅ Queued {saved} receipt(s) for translation.")
            st.rerun()

    pending = ss.list_uploads()
    st.markdown("---")
    st.markdown(f"#### 📥 Queued for translation ({len(pending)})")
    if not pending:
        st.info("No receipts queued. Upload above to begin.")
        return
    for rec in pending:
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 3, 1])
            with c1:
                _preview_receipt(
                    ss, ss.SCANNER_STAGE_UPLOAD, rec["receipt_id"], rec["filename"]
                )
            with c2:
                st.write(f"**{rec['original_name']}**")
                st.caption(f"ID: `{rec['receipt_id']}`")
                st.caption("Open **Translate & Push** to process this receipt.")
            with c3:
                if st.button("🗑 Discard", key=f"disc1_{rec['receipt_id']}"):
                    ss.discard(rec["receipt_id"], ss.SCANNER_STAGE_UPLOAD)
                    st.rerun()


def _stage2_translate_ui(ss, df, save_fn, sheet, keys, has_ai,
                         dropdown_options, all_categories, all_units):
    """Stage 2 — translate queued receipts, then edit and push them."""
    # Section A — awaiting translation
    awaiting = ss.list_uploads()
    st.markdown(f"#### 🌐 Awaiting translation ({len(awaiting)})")
    if not awaiting:
        st.caption("Nothing waiting. Upload receipts in the **Upload** tab.")
    for rec in awaiting:
        with st.container(border=True):
            c1, c2 = st.columns([1, 4])
            with c1:
                _preview_receipt(
                    ss, ss.SCANNER_STAGE_UPLOAD, rec["receipt_id"],
                    rec["filename"], width=120,
                )
            with c2:
                st.write(f"**{rec['original_name']}**  ·  `{rec['receipt_id']}`")
                if st.button("🌐 Translate", key=f"tr_{rec['receipt_id']}",
                             type="primary"):
                    data = ss.read_receipt_bytes(
                        ss.SCANNER_STAGE_UPLOAD, rec["receipt_id"]
                    )
                    if not data:
                        st.error("Could not read the receipt file.")
                    else:
                        parsed, provider = _run_extraction(
                            data, rec["original_name"], keys, has_ai,
                            dropdown_options,
                        )
                        if not parsed or (not parsed.get("items")
                                          and "error" in parsed):
                            st.error("❌ Could not extract data. Try a clearer file.")
                        else:
                            ss.translate_promote(
                                rec["receipt_id"], parsed, provider
                            )
                            st.success(f"✅ Translated using **{provider or 'OCR'}**")
                            st.rerun()

    st.markdown("---")

    # Section B — translated, ready to edit & push
    translated = ss.list_translated()
    st.markdown(f"#### ✏️ Translated — edit & push ({len(translated)})")
    if not translated:
        st.info("No translated receipts yet.")
        return
    for record in translated:
        rid = record["receipt_id"]
        data = record.get("data", {}) or {}
        title = (
            f"🧾 {record.get('original_name', rid)}  ·  "
            f"{data.get('shop', 'Unknown')}  ·  "
            f"{data.get('total', '?')} {data.get('currency', 'SEK')}"
        )
        with st.expander(title):
            _edit_and_push_one(
                ss, record, df, save_fn, sheet,
                all_categories, all_units,
            )


def _edit_and_push_one(ss, record, df, save_fn, sheet, all_categories, all_units):
    """Editable form for one translated receipt: save edits or push to table."""
    rid = record["receipt_id"]
    data = record.get("data", {}) or {}

    cprev, cform = st.columns([1, 3])
    with cprev:
        _preview_receipt(
            ss, ss.SCANNER_STAGE_TRANSLATED, rid,
            record.get("receipt_filename", ""), width=180,
        )
    with cform:
        c1, c2 = st.columns(2)
        with c1:
            date_val = data.get("date") or date.today()
            if isinstance(date_val, str):
                try:
                    date_val = date.fromisoformat(date_val)
                except Exception:  # noqa: BLE001
                    date_val = date.today()
            receipt_date = st.date_input("Date", value=date_val, key=f"d_{rid}")
            shop = st.text_input("Shop", value=data.get("shop", "Unknown"),
                                 key=f"s_{rid}")
        with c2:
            currency = data.get("currency", "SEK")
            total = st.number_input(
                f"Total ({currency})",
                value=float(data.get("total", 0) or 0),
                min_value=0.0, step=0.01, key=f"t_{rid}",
            )

    raw_items = data.get("items", [])
    items_df = pd.DataFrame(raw_items) if raw_items else pd.DataFrame(
        columns=["name", "price", "quantity", "quantity_unit",
                 "category", "subcategory"]
    )
    for col in ("name", "price", "quantity", "quantity_unit",
                "category", "subcategory"):
        if col not in items_df.columns:
            if col == "name":
                items_df[col] = ""
            elif col in ("price", "quantity"):
                items_df[col] = 0.0
            elif col == "quantity_unit":
                items_df[col] = "pcs"
            elif col == "category":
                items_df[col] = "Groceries"
            else:
                items_df[col] = "General"

    col_order = ["name", "price", "quantity", "quantity_unit",
                 "category", "subcategory"]
    items_df = items_df[[c for c in col_order if c in items_df.columns]]

    ai_cats = (items_df["category"].dropna().unique().tolist()
               if "category" in items_df.columns else [])
    merged_categories = sorted(set(all_categories) | set(ai_cats))

    edited = st.data_editor(
        items_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "name":          st.column_config.TextColumn("Item", required=True),
            "price":         st.column_config.NumberColumn("Price", min_value=0.0, format="%.2f"),
            "quantity":      st.column_config.NumberColumn("Qty", min_value=0.0, format="%.3f"),
            "quantity_unit": st.column_config.SelectboxColumn(
                "Unit", options=all_units, required=True, help="Select a unit",
            ),
            "category": st.column_config.TextColumn(
                "Category",
                help="Type any category, or use one of: " + ", ".join(merged_categories),
                required=True,
            ),
            "subcategory": st.column_config.TextColumn(
                "Subcategory", help="Type any subcategory freely",
            ),
        },
        key=f"items_{rid}",
    )

    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button("💾 Save edits", key=f"save_{rid}"):
            data["date"] = str(receipt_date)
            data["shop"] = shop
            data["total"] = float(total)
            data["currency"] = currency
            data["items"] = edited.fillna("").to_dict("records")
            ss.save_translation(rid, data)
            st.success("Saved.")
            st.rerun()
    with b2:
        if st.button("✅ Push to Expense Table", key=f"push_{rid}",
                     type="primary"):
            rows = _build_expense_rows(edited, receipt_date, shop, currency)
            if not rows:
                st.error("No valid items to push.")
            else:
                updated = pd.concat([df, pd.DataFrame(rows)], ignore_index=True)
                save_fn(updated, sheet)
                ss.push_promote(rid)
                try:
                    from data_manager import bump_data_version
                    bump_data_version()
                except Exception:  # noqa: BLE001
                    pass
                st.success(f"✅ Pushed {len(rows)} items — receipt archived.")
                st.balloons()
                st.rerun()
    with b3:
        if st.button("🗑 Discard", key=f"disc2_{rid}"):
            ss.discard(rid, ss.SCANNER_STAGE_TRANSLATED)
            st.rerun()


def _build_expense_rows(edited_items, receipt_date, shop, currency):
    """Convert the edited item rows into expense-table records."""
    from config import Columns

    rows = []
    for _, item in edited_items.iterrows():
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        qty = float(item.get("quantity", 1.0) or 1.0)
        price = float(item.get("price", 0.0) or 0.0)
        unit = str(item.get("quantity_unit", "pcs") or "pcs")
        cat = str(item.get("category", "Groceries") or "Groceries")
        sub = str(item.get("subcategory", "") or "")
        rows.append({
            Columns.DATE:           pd.to_datetime(receipt_date).date(),
            Columns.EXPENSE_TYPE:   "Goods",
            Columns.SHOP:           shop,
            Columns.CATEGORY:       cat,
            Columns.SUBCATEGORY:    sub,
            Columns.ITEM:           name,
            Columns.BRAND:          "",
            Columns.QUANTITY:       qty,
            Columns.QUANTITY_UNIT:  unit,
            Columns.PRICE_PAID:     price,
            Columns.CURRENCY:       currency,
            Columns.PRICE_PER_UNIT: price / qty if qty > 0 else price,
        })
    return rows


def _stage3_archive_ui(ss):
    """Stage 3 — receipts archived after being pushed to the expense table."""
    archive = ss.list_archive()
    st.markdown(f"#### 📁 Archived receipts ({len(archive)})")
    st.caption(
        "Receipts whose data was pushed to the expense table. "
        "Stored in the **Final** folder (local + Google Drive)."
    )
    if not archive:
        st.info("No archived receipts yet.")
        return
    cols = st.columns(4)
    for i, rec in enumerate(archive):
        with cols[i % 4]:
            with st.container(border=True):
                _preview_receipt(
                    ss, ss.SCANNER_STAGE_FINAL, rec["receipt_id"],
                    rec["filename"], width=140,
                )
                st.caption(rec["original_name"])


def _show_ocr_instructions():
    st.info(
        "**📸 Tips for Best Results:**\n"
        "- Photograph in good lighting, receipt flat and in focus\n"
        "- Avoid shadows, glare, and cut-off edges\n"
        "- With an AI key: one click extracts, translates, and categorises everything\n"
        "- Without an AI key: free OCR + MyMemory translation is used automatically"
    )
