# receipt_ocr.py
"""
Receipt OCR with Swedish translation support.

Extracts text from receipt images via Google Cloud Vision API or
pytesseract, translates Swedish to English, then parses structured
expense data (date, shop, total, line items).

Falls back to manual entry if no OCR backend is available.
"""
import re
import requests
import streamlit as st
from typing import Optional


# ===============================================================
# DEPENDENCY CHECK
# ===============================================================

def _check_ocr_available() -> tuple:
    """
    Returns (tesseract_ok: bool, pillow_ok: bool, message: str).
    """
    pillow_ok = False
    tesseract_ok = False
    msg = []

    try:
        from PIL import Image  # noqa: F401
        pillow_ok = True
    except ImportError:
        msg.append("Pillow not installed (`pip install Pillow`)")

    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        tesseract_ok = True
    except ImportError:
        msg.append("pytesseract not installed (`pip install pytesseract`)")
    except Exception:
        msg.append(
            "Tesseract binary not found. "
            "Install with: `sudo apt install tesseract-ocr tesseract-ocr-swe` (Ubuntu) "
            "or `brew install tesseract` (macOS)"
        )

    return tesseract_ok, pillow_ok, " | ".join(msg)


# ===============================================================
# CORE OCR
# ===============================================================

def extract_text_from_image(uploaded_file, api_key: str = None) -> tuple:
    """
    Extract text from a receipt image.

    Priority:
      1. Google Cloud Vision API  (if api_key provided)
      2. pytesseract              (if installed + Tesseract binary present)
      3. Returns ("", 0.0)        (caller handles gracefully)

    Returns:
        (text: str, confidence: float)
    """
    import io

    image_bytes = uploaded_file.read()
    uploaded_file.seek(0)

    # ── 1. Google Cloud Vision ────────────────────────────────
    if api_key:
        try:
            import base64
            encoded = base64.b64encode(image_bytes).decode("utf-8")
            url = (
                "https://vision.googleapis.com/v1/images:annotate"
                f"?key={api_key}"
            )
            payload = {
                "requests": [{
                    "image": {"content": encoded},
                    "features": [{"type": "TEXT_DETECTION"}],
                }]
            }
            resp = requests.post(url, json=payload, timeout=15)
            resp.raise_for_status()
            annotations = (
                resp.json()["responses"][0].get("textAnnotations", [])
            )
            if annotations:
                return annotations[0]["description"], 0.95
            return "", 0.0
        except Exception as e:
            st.warning(f"Vision API failed: {e}. Trying local OCR…")

    # ── 2. pytesseract ────────────────────────────────────────
    try:
        import pytesseract
        from PIL import Image

        image = Image.open(io.BytesIO(image_bytes))
        # Try Swedish + English; fall back to English-only
        try:
            text = pytesseract.image_to_string(image, lang="swe+eng")
        except pytesseract.TesseractError:
            text = pytesseract.image_to_string(image, lang="eng")

        return text.strip(), 0.75 if text.strip() else 0.0

    except ImportError:
        pass
    except Exception as e:
        st.warning(f"pytesseract error: {e}")

    return "", 0.0


# ===============================================================
# RECEIPT PARSER
# ===============================================================

def parse_receipt_text(text: str) -> dict:
    """
    Parse plain-text receipt content into structured data.

    Returns:
        {
            "date":  datetime.date,
            "shop":  str,
            "total": float,
            "items": [{"name": str, "price": float, "quantity": float}, ...]
        }
    """
    from datetime import datetime, date as _date

    if not text:
        return {"date": _date.today(), "shop": "Unknown", "total": 0.0, "items": []}

    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # ── Date ─────────────────────────────────────────────────
    parsed_date = None
    date_patterns = [
        r"\b(\d{4}[-/]\d{2}[-/]\d{2})\b",
        r"\b(\d{2}[-/]\d{2}[-/]\d{4})\b",
        r"\b(\d{2}[-/]\d{2}[-/]\d{2})\b",
    ]
    for pattern in date_patterns:
        for line in lines:
            m = re.search(pattern, line)
            if m:
                for fmt in (
                    "%Y-%m-%d", "%Y/%m/%d",
                    "%d-%m-%Y", "%d/%m/%Y",
                    "%d-%m-%y", "%d/%m/%y",
                ):
                    try:
                        parsed_date = datetime.strptime(m.group(1), fmt).date()
                        break
                    except ValueError:
                        continue
            if parsed_date:
                break
        if parsed_date:
            break
    if parsed_date is None:
        parsed_date = _date.today()

    # ── Shop ─────────────────────────────────────────────────
    shop = lines[0] if lines else "Unknown"

    # ── Total ─────────────────────────────────────────────────
    total = 0.0
    total_patterns = [
        r"(?:total|totalt|summa|att\s+betala)[^\d]*(\d+[.,]\d{2})",
        r"(\d+[.,]\d{2})\s*(?:sek|kr)?$",
    ]
    for pattern in total_patterns:
        for line in reversed(lines):
            m = re.search(pattern, line, re.IGNORECASE)
            if m:
                try:
                    total = float(m.group(1).replace(",", "."))
                    break
                except ValueError:
                    pass
        if total:
            break

    # ── Line items ────────────────────────────────────────────
    items = []
    item_pattern = re.compile(
        r"^(.+?)\s+(\d+(?:[.,]\d+)?)\s*(?:x\s*(\d+(?:[.,]\d+)?))?$"
    )
    skip_keywords = {
        "total", "totalt", "summa", "moms", "vat",
        "datum", "kvitto", "receipt", "date", "time", "tid", "betalning",
    }
    for line in lines[1:]:
        if any(kw in line.lower() for kw in skip_keywords):
            continue
        m = item_pattern.match(line)
        if m:
            name = m.group(1).strip()
            try:
                price = float(m.group(2).replace(",", "."))
            except ValueError:
                continue
            quantity = 1.0
            if m.group(3):
                try:
                    quantity = float(m.group(3).replace(",", "."))
                except ValueError:
                    pass
            if price > 0 and len(name) > 1:
                items.append({"name": name, "price": price, "quantity": quantity})

    # Fallback single row
    if not items and total > 0:
        items.append({"name": "Receipt Items", "price": total, "quantity": 1.0})

    return {"date": parsed_date, "shop": shop, "total": total, "items": items}


# ===============================================================
# SWEDISH TRANSLATION
# ===============================================================

def translate_swedish_to_english(text: str, api_key: Optional[str] = None) -> str:
    """Translate Swedish receipt text to English."""
    if not text or not text.strip():
        return text
    if api_key:
        try:
            return _translate_with_google_api(text, api_key)
        except Exception:
            pass
    return _translate_with_dictionary(text)


def _translate_with_google_api(text: str, api_key: str) -> str:
    url = "https://translation.googleapis.com/language/translate/v2"
    params = {"key": api_key, "q": text, "source": "sv", "target": "en", "format": "text"}
    response = requests.post(url, params=params, timeout=10)
    response.raise_for_status()
    return response.json()["data"]["translations"][0]["translatedText"]


def _translate_with_dictionary(text: str) -> str:
    SWEDISH_TO_ENGLISH = {
        "mjolk": "milk", "mjölk": "milk", "filmjolk": "buttermilk",
        "yoghurt": "yogurt", "gradde": "cream", "grädde": "cream",
        "smor": "butter", "smör": "butter", "margarin": "margarine",
        "ost": "cheese", "agg": "eggs", "ägg": "eggs",
        "kott": "meat", "kött": "meat", "flask": "pork", "fläsk": "pork",
        "notkott": "beef", "nötkött": "beef", "kyckling": "chicken",
        "korv": "sausage", "bacon": "bacon", "skinka": "ham",
        "fisk": "fish", "lax": "salmon", "rakor": "shrimp", "räkor": "shrimp",
        "brod": "bread", "bröd": "bread", "knackebrod": "crispbread",
        "bulle": "bun", "kakor": "cookies", "kaka": "cake",
        "apple": "apple", "äpple": "apple", "banan": "banana",
        "apelsin": "orange", "paron": "pear", "päron": "pear",
        "druvor": "grapes", "jordgubbar": "strawberries",
        "blabar": "blueberries", "blåbär": "blueberries",
        "hallon": "raspberries",
        "tomat": "tomato", "gurka": "cucumber", "morot": "carrot",
        "lok": "onion", "lök": "onion", "vitlok": "garlic", "vitlök": "garlic",
        "potatis": "potato", "paprika": "bell pepper", "sallad": "lettuce",
        "broccoli": "broccoli", "blomkal": "cauliflower", "blomkål": "cauliflower",
        "kaffe": "coffee", "te": "tea", "juice": "juice",
        "vatten": "water", "lask": "soda", "läsk": "soda",
        "ol": "beer", "öl": "beer", "vin": "wine",
        "ris": "rice", "pasta": "pasta", "mjol": "flour", "mjöl": "flour",
        "socker": "sugar", "salt": "salt", "peppar": "pepper",
        "olja": "oil", "attika": "vinegar", "ättika": "vinegar",
        "senap": "mustard", "ketchup": "ketchup",
        "kvitto": "receipt", "totalt": "total", "summa": "sum",
        "moms": "vat", "datum": "date", "tid": "time",
        "st": "pcs", "kg": "kg", "liter": "liter",
        "paket": "package", "forpackning": "package", "förpackning": "package",
        "kop": "purchase", "köp": "purchase",
        "betalning": "payment", "kort": "card", "kontant": "cash",
    }
    result = text
    for swedish, english in SWEDISH_TO_ENGLISH.items():
        pattern = r"\b" + re.escape(swedish) + r"\b"
        result = re.sub(pattern, english, result, flags=re.IGNORECASE)
    return result


# ===============================================================
# COMBINED PIPELINE
# ===============================================================

def extract_with_translation(
    uploaded_file,
    google_vision_key: Optional[str] = None,
    translate_api_key: Optional[str] = None,
) -> tuple:
    """
    Full pipeline: OCR -> translate -> parse.

    Returns:
        (parsed_data: dict, raw_text_swedish: str, raw_text_english: str)
        parsed_data is {} on failure.
    """
    raw_text_swedish, confidence = extract_text_from_image(
        uploaded_file, google_vision_key
    )
    if not raw_text_swedish:
        return {}, "", ""

    raw_text_english = translate_swedish_to_english(raw_text_swedish, translate_api_key)
    parsed_data = parse_receipt_text(raw_text_english)
    return parsed_data, raw_text_swedish, raw_text_english


# ===============================================================
# MANUAL ENTRY FALLBACK
# ===============================================================

def _manual_entry_form(df, save_fn, sheet):
    """Full manual entry form shown when OCR is unavailable."""
    import pandas as pd
    from datetime import date
    from config import Columns
    from data_manager import bump_data_version

    st.info(
        "Enter receipt details manually below. "
        "You can add as many items as needed."
    )

    c1, c2 = st.columns(2)
    with c1:
        exp_date = st.date_input("Date", value=date.today(), key="manual_date")
        shop = st.text_input("Shop / Store", placeholder="e.g. ICA Maxi", key="manual_shop")
    with c2:
        currency = st.selectbox("Currency", ["SEK", "EUR", "USD", "INR"], key="manual_cur")

    st.markdown("#### Items")

    if "manual_items" not in st.session_state:
        st.session_state["manual_items"] = [
            {"name": "", "price": 0.0, "quantity": 1.0}
        ]

    for i, item in enumerate(st.session_state["manual_items"]):
        ic1, ic2, ic3, ic4 = st.columns([3, 1, 1, 0.4])
        with ic1:
            name = st.text_input(
                "Item", value=item["name"],
                placeholder="e.g. Milk", key=f"mi_name_{i}",
                label_visibility="collapsed" if i > 0 else "visible",
            )
        with ic2:
            price = st.number_input(
                "Price", value=float(item["price"]),
                min_value=0.0, step=1.0, key=f"mi_price_{i}",
                label_visibility="collapsed" if i > 0 else "visible",
            )
        with ic3:
            qty = st.number_input(
                "Qty", value=float(item["quantity"]),
                min_value=0.01, step=1.0, key=f"mi_qty_{i}",
                label_visibility="collapsed" if i > 0 else "visible",
            )
        with ic4:
            if i > 0:
                if st.button("✕", key=f"mi_del_{i}"):
                    st.session_state["manual_items"].pop(i)
                    st.rerun()
        st.session_state["manual_items"][i] = {
            "name": name, "price": price, "quantity": qty
        }

    if st.button("＋ Add Row"):
        st.session_state["manual_items"].append(
            {"name": "", "price": 0.0, "quantity": 1.0}
        )
        st.rerun()

    st.markdown("---")
    if st.button("💾 Save to Expense Tracker", type="primary"):
        valid_items = [
            it for it in st.session_state["manual_items"]
            if it["name"].strip() and it["price"] > 0
        ]
        if not valid_items:
            st.error("Please add at least one item with a name and price > 0.")
            return

        new_rows = []
        for it in valid_items:
            qty = it["quantity"]
            price = it["price"]
            new_rows.append({
                Columns.DATE:           pd.to_datetime(exp_date).date(),
                Columns.EXPENSE_TYPE:   "Goods",
                Columns.SHOP:           shop or "Unknown",
                Columns.CATEGORY:       "Groceries",
                Columns.SUBCATEGORY:    "",
                Columns.ITEM:           it["name"].strip(),
                Columns.BRAND:          "",
                Columns.QUANTITY:       qty,
                Columns.QUANTITY_UNIT:  "pcs",
                Columns.PRICE_PAID:     price,
                Columns.CURRENCY:       currency,
                Columns.PRICE_PER_UNIT: round(price / qty, 2) if qty > 0 else price,
            })

        updated_df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
        save_fn(updated_df, sheet)
        st.success(f"Saved {len(new_rows)} item(s)!")
        st.session_state.pop("manual_items", None)
        bump_data_version()
        st.rerun()


# ===============================================================
# MAIN UI
# ===============================================================

def receipt_upload_ui_with_translation(df, save_fn, sheet=None):

    import streamlit as st
    import pandas as pd
    from config import Columns
    from data_manager import bump_data_version

    st.title("📷 Receipt Scanner")
    st.markdown(
        "Upload a receipt and verify extracted data before adding expenses."
    )

    # ============================================================
    # API SETTINGS
    # ============================================================

    with st.expander("⚙️ Optional API Keys"):

        vision_key = st.text_input(
            "Google Vision API Key",
            type="password"
        )

        translate_key = st.text_input(
            "Google Translation API Key",
            type="password"
        )

    # ============================================================
    # FILE UPLOAD
    # ============================================================

    uploaded_file = st.file_uploader(
        "Upload Receipt",
        type=["jpg", "jpeg", "png"]
    )

    if not uploaded_file:
        _show_ocr_instructions()
        return

    st.image(uploaded_file, caption="Uploaded Receipt")

    # ============================================================
    # OCR EXTRACTION
    # ============================================================

    if st.button("🔍 Scan Receipt", type="primary"):

        with st.spinner("Extracting receipt data..."):

            parsed, text_sv, text_en = extract_with_translation(
                uploaded_file,
                vision_key if vision_key else None,
                translate_key if translate_key else None
            )

            if not parsed or "error" in parsed:
                st.error("Could not extract receipt data.")
                return

            # STORE IN SESSION STATE
            st.session_state["receipt_review"] = {
                "parsed": parsed,
                "text_sv": text_sv,
                "text_en": text_en,
            }

            st.success("Receipt scanned successfully!")

    # ============================================================
    # REVIEW SCREEN
    # ============================================================

    if "receipt_review" not in st.session_state:
        return

    review = st.session_state["receipt_review"]

    parsed = review["parsed"]

    text_sv = review["text_sv"]
    text_en = review["text_en"]

    # ============================================================
    # OCR TEXT PREVIEW
    # ============================================================

    with st.expander("📄 OCR Extracted Text"):

        tab1, tab2 = st.tabs([
            "🇸🇪 Swedish",
            "🇬🇧 English"
        ])

        with tab1:
            st.code(text_sv)

        with tab2:
            st.code(text_en)

    # ============================================================
    # EDITABLE HEADER FIELDS
    # ============================================================

    st.markdown("## ✏️ Review Receipt")

    col1, col2 = st.columns(2)

    with col1:

        date = st.date_input(
            "Date",
            value=parsed.get("date")
        )

        shop = st.text_input(
            "Shop",
            value=parsed.get("shop", "Unknown")
        )

    with col2:

        total = st.number_input(
            "Total Amount",
            value=float(parsed.get("total", 0)),
            min_value=0.0,
            step=0.01
        )

        category = st.selectbox(
            "Category",
            [
                "Groceries",
                "Food",
                "Transport",
                "Shopping",
                "Bills",
                "Entertainment",
                "Travel",
                "Health",
                "Other"
            ]
        )

    # ============================================================
    # ITEMS EDITOR
    # ============================================================

    st.markdown("## 🧾 Edit Items")

    items = parsed.get("items", [])

    if not items:
        items = [{
            "name": "",
            "price": 0.0,
            "quantity": 1.0
        }]

    items_df = pd.DataFrame(items)

    edited_items = st.data_editor(
        items_df,
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        column_config={
            "name": st.column_config.TextColumn(
                "Item",
                required=True
            ),
            "price": st.column_config.NumberColumn(
                "Price",
                min_value=0.0,
                format="%.2f"
            ),
            "quantity": st.column_config.NumberColumn(
                "Quantity",
                min_value=0.0,
                format="%.2f"
            ),
        }
    )

    # ============================================================
    # ACTION BUTTONS
    # ============================================================

    col1, col2 = st.columns(2)

    # ------------------------------------------------------------
    # APPROVE & SAVE
    # ------------------------------------------------------------

    with col1:

        if st.button(
            "✅ Approve & Add Expense",
            type="primary",
            width="stretch"
        ):

            if edited_items.empty:
                st.error("No items to save.")
                return

            new_rows = []

            for _, item in edited_items.iterrows():

                quantity = item.get("quantity", 1.0)

                if quantity <= 0:
                    quantity = 1.0

                row = {
                    Columns.DATE:
                        pd.to_datetime(date).date(),

                    Columns.EXPENSE_TYPE:
                        "Goods",

                    Columns.SHOP:
                        shop,

                    Columns.CATEGORY:
                        category,

                    Columns.SUBCATEGORY:
                        "",

                    Columns.ITEM:
                        item["name"],

                    Columns.BRAND:
                        "",

                    Columns.QUANTITY:
                        quantity,

                    Columns.QUANTITY_UNIT:
                        "pcs",

                    Columns.PRICE_PAID:
                        float(item["price"]),

                    Columns.CURRENCY:
                        "SEK",

                    Columns.PRICE_PER_UNIT:
                        float(item["price"]) / quantity,
                }

                new_rows.append(row)

            updated_df = pd.concat(
                [df, pd.DataFrame(new_rows)],
                ignore_index=True
            )

            save_fn(updated_df, sheet)

            bump_data_version()

            del st.session_state["receipt_review"]

            st.success(
                f"✅ Successfully added {len(new_rows)} expenses!"
            )

            st.balloons()

            st.rerun()

    # ------------------------------------------------------------
    # CANCEL BUTTON
    # ------------------------------------------------------------

    with col2:

        if st.button(
            "❌ Cancel",
            width="stretch"
        ):

            del st.session_state["receipt_review"]

            st.warning("Receipt discarded.")

            st.rerun()


def _show_ocr_instructions():
    st.info(
        """
        **Tips for best OCR results:**
        - Good lighting, no shadows or glare
        - Receipt flat and fully in frame
        - Photo in focus
        - Swedish receipts are auto-translated
        """
    )
