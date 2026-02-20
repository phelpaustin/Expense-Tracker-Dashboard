# receipt_ocr_swedish_translation.py
"""
Swedish Translation Enhancement for receipt_ocr.py

Adds automatic translation of Swedish receipts to English before parsing.
Works with or without Google Cloud Translation API.

INTEGRATION: Add these functions to your existing receipt_ocr.py file.
"""
import re
import requests
import streamlit as st
from typing import Optional, Dict


# ═══════════════════════════════════════════════════════════════
# SWEDISH TO ENGLISH TRANSLATION
# ═══════════════════════════════════════════════════════════════

def translate_swedish_to_english(text: str, api_key: Optional[str] = None) -> str:
    """
    Translate Swedish receipt text to English.
    
    Args:
        text: Raw Swedish text from receipt
        api_key: Optional Google Cloud Translation API key
    
    Returns:
        Translated English text
    """
    if not text or not text.strip():
        return text
    
    # Try Google Translate API first (if key provided)
    if api_key:
        try:
            return _translate_with_google_api(text, api_key)
        except Exception as e:
            # Fall back to dictionary translation
            pass
    
    # Fallback: Dictionary-based translation
    return _translate_with_dictionary(text)


def _translate_with_google_api(text: str, api_key: str) -> str:
    """Translate using Google Cloud Translation API."""
    url = "https://translation.googleapis.com/language/translate/v2"
    params = {
        "key": api_key,
        "q": text,
        "source": "sv",
        "target": "en",
        "format": "text"
    }
    
    response = requests.post(url, params=params, timeout=10)
    response.raise_for_status()
    
    result = response.json()
    return result["data"]["translations"][0]["translatedText"]


def _translate_with_dictionary(text: str) -> str:
    """
    Translate using a comprehensive Swedish-English dictionary.
    Covers common grocery and household items found on receipts.
    """
    # Comprehensive Swedish-English mapping
    SWEDISH_TO_ENGLISH = {
        # Dairy
        "mjölk": "milk",
        "filmjölk": "buttermilk",
        "yoghurt": "yogurt",
        "grädde": "cream",
        "smör": "butter",
        "margarin": "margarine",
        "ost": "cheese",
        "ägg": "eggs",
        
        # Meat & Fish
        "kött": "meat",
        "fläsk": "pork",
        "nötkött": "beef",
        "kyckling": "chicken",
        "korv": "sausage",
        "bacon": "bacon",
        "skinka": "ham",
        "fisk": "fish",
        "lax": "salmon",
        "räkor": "shrimp",
        
        # Bread & Bakery
        "bröd": "bread",
        "knäckebröd": "crispbread",
        "bulle": "bun",
        "kakor": "cookies",
        "kaka": "cake",
        
        # Fruits
        "äpple": "apple",
        "banan": "banana",
        "apelsin": "orange",
        "päron": "pear",
        "druvor": "grapes",
        "jordgubbar": "strawberries",
        "blåbär": "blueberries",
        "hallon": "raspberries",
        
        # Vegetables
        "tomat": "tomato",
        "gurka": "cucumber",
        "morot": "carrot",
        "lök": "onion",
        "vitlök": "garlic",
        "potatis": "potato",
        "paprika": "bell pepper",
        "sallad": "lettuce",
        "broccoli": "broccoli",
        "blomkål": "cauliflower",
        
        # Beverages
        "kaffe": "coffee",
        "te": "tea",
        "juice": "juice",
        "vatten": "water",
        "läsk": "soda",
        "öl": "beer",
        "vin": "wine",
        
        # Pantry
        "ris": "rice",
        "pasta": "pasta",
        "mjöl": "flour",
        "socker": "sugar",
        "salt": "salt",
        "peppar": "pepper",
        "olja": "oil",
        "ättika": "vinegar",
        "senap": "mustard",
        "ketchup": "ketchup",
        
        # Common words on receipts
        "kvitto": "receipt",
        "totalt": "total",
        "summa": "sum",
        "moms": "vat",
        "datum": "date",
        "tid": "time",
        "st": "pcs",  # pieces (styck)
        "kg": "kg",
        "liter": "liter",
        "paket": "package",
        "förpackning": "package",
        
        # Stores
        "ica": "ica",
        "coop": "coop",
        "willys": "willys",
        "lidl": "lidl",
        "hemköp": "hemkop",
        
        # Actions
        "köp": "purchase",
        "betalning": "payment",
        "kort": "card",
        "kontant": "cash",
    }
    
    # Convert to lowercase for matching
    text_lower = text.lower()
    result = text
    
    # Replace Swedish words with English equivalents
    for swedish, english in SWEDISH_TO_ENGLISH.items():
        # Word boundary replacement to avoid partial matches
        pattern = r'\b' + re.escape(swedish) + r'\b'
        result = re.sub(pattern, english, result, flags=re.IGNORECASE)
    
    return result


def extract_with_translation(uploaded_file, google_vision_key: Optional[str] = None,
                            translate_api_key: Optional[str] = None) -> tuple:
    """
    Complete receipt extraction with Swedish translation support.
    
    Args:
        uploaded_file: Streamlit uploaded file object
        google_vision_key: Optional Google Cloud Vision API key for OCR
        translate_api_key: Optional Google Cloud Translation API key
    
    Returns:
        (parsed_data_dict, raw_text_swedish, raw_text_english)
    """
    # Step 1: Extract text from image (existing function)
    from receipt_ocr import extract_text_from_image
    raw_text_swedish, confidence = extract_text_from_image(uploaded_file, google_vision_key)
    
    if not raw_text_swedish:
        return {}, "", ""
    
    # Step 2: Translate Swedish to English
    raw_text_english = translate_swedish_to_english(raw_text_swedish, translate_api_key)
    
    # Step 3: Parse the English text (existing function)
    from receipt_ocr import parse_receipt_text
    parsed_data = parse_receipt_text(raw_text_english)
    
    return parsed_data, raw_text_swedish, raw_text_english


# ═══════════════════════════════════════════════════════════════
# UPDATED UI FUNCTION FOR receipt_ocr.py
# ═══════════════════════════════════════════════════════════════

def receipt_upload_ui_with_translation(df, save_fn, sheet=None):
    """
    Updated receipt upload UI with Swedish translation support.
    
    REPLACE the existing receipt_upload_ui() in receipt_ocr.py with this function.
    """
    import streamlit as st
    from config import Columns
    
    st.title("📷 Receipt Scanner")
    st.markdown("Upload a photo of your receipt to automatically extract items and amounts.")
    
    # API key inputs (optional)
    with st.expander("⚙️ Optional: API Keys for Better Accuracy"):
        st.markdown("""
        For best results, provide Google Cloud API keys:
        - **Vision API**: More accurate text extraction
        - **Translation API**: Automatic Swedish → English translation
        
        [Get API Keys](https://console.cloud.google.com/apis/credentials)
        """)
        
        vision_key = st.text_input(
            "Google Cloud Vision API Key",
            type="password",
            help="Improves OCR accuracy"
        )
        translate_key = st.text_input(
            "Google Cloud Translation API Key",
            type="password",
            help="Auto-translates Swedish receipts"
        )
    
    # File upload
    uploaded_file = st.file_uploader(
        "Upload Receipt Image",
        type=["jpg", "jpeg", "png"],
        help="Take a clear photo of the receipt"
    )
    
    if not uploaded_file:
        _show_ocr_instructions()
        return
    
    # Show uploaded image
    st.image(uploaded_file, caption="Uploaded Receipt", width="stretch")
    
    # Process button
    if st.button("🔍 Extract & Translate", type="primary"):
        with st.spinner("Processing receipt..."):
            # Extract with translation
            parsed, text_sv, text_en = extract_with_translation(
                uploaded_file,
                vision_key if vision_key else None,
                translate_key if translate_key else None
            )
            
            if not parsed or "error" in parsed:
                st.error("❌ Could not extract data from receipt. Please try a clearer photo.")
                return
            
            # Show extracted text (with translation toggle)
            with st.expander("📄 Extracted Text"):
                tab1, tab2 = st.tabs(["🇸🇪 Swedish (Original)", "🇬🇧 English (Translated)"])
                with tab1:
                    st.code(text_sv, language="text")
                with tab2:
                    st.code(text_en, language="text")
            
            # Editable parsed data
            st.markdown("### ✏️ Verify Extracted Information")
            
            col1, col2 = st.columns(2)
            with col1:
                date = st.date_input("Date", value=parsed.get("date"))
                shop = st.text_input("Shop", value=parsed.get("shop", "Unknown"))
            with col2:
                total = st.number_input(
                    "Total Amount (SEK)",
                    value=float(parsed.get("total", 0)),
                    min_value=0.0,
                    step=0.01
                )
            
            # Items
            st.markdown("### 🧾 Items")
            items = parsed.get("items", [])
            
            if items:
                # Show items in editable dataframe
                import pandas as pd
                items_df = pd.DataFrame(items)
                edited_items = st.data_editor(
                    items_df,
                    num_rows="dynamic",
                    width="stretch",
                    column_config={
                        "name": st.column_config.TextColumn("Item Name", required=True),
                        "price": st.column_config.NumberColumn("Price (SEK)", min_value=0, format="%.2f"),
                        "quantity": st.column_config.NumberColumn("Quantity", min_value=0, format="%.2f"),
                    }
                )
            else:
                st.warning("No items detected. Add manually below.")
                edited_items = pd.DataFrame(columns=["name", "price", "quantity"])
            
            # Save button
            if st.button("💾 Save to Expense Tracker", type="primary"):
                if edited_items.empty:
                    st.error("No items to save!")
                    return
                
                # Build expense entries
                new_rows = []
                for _, item in edited_items.iterrows():
                    row = {
                        Columns.DATE: pd.to_datetime(date).date(),
                        Columns.EXPENSE_TYPE: "Goods",
                        Columns.SHOP: shop,
                        Columns.CATEGORY: "Groceries",  # Default, user can edit later
                        Columns.SUBCATEGORY: "",
                        Columns.ITEM: item["name"],
                        Columns.BRAND: "",
                        Columns.QUANTITY: item.get("quantity", 1.0),
                        Columns.QUANTITY_UNIT: "pcs",
                        Columns.PRICE_PAID: item["price"],
                        Columns.CURRENCY: "SEK",
                        Columns.PRICE_PER_UNIT: item["price"] / item.get("quantity", 1.0) if item.get("quantity", 1.0) > 0 else item["price"],
                    }
                    new_rows.append(row)
                
                # Save
                updated_df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
                save_fn(updated_df, sheet)
                
                st.success(f"✅ Added {len(new_rows)} items from receipt!")
                st.balloons()
                
                from data_manager import bump_data_version
                bump_data_version()
                st.rerun()


def _show_ocr_instructions():
    """Show tips for best OCR results."""
    st.info("""
    **📸 Tips for Best Results:**
    - Take photo in good lighting
    - Ensure receipt is flat and in focus
    - Avoid shadows and glare
    - Include the entire receipt
    - Swedish receipts are auto-translated to English!
    """)


# ═══════════════════════════════════════════════════════════════
# INTEGRATION INSTRUCTIONS
# ═══════════════════════════════════════════════════════════════
"""
TO INTEGRATE SWEDISH TRANSLATION INTO YOUR receipt_ocr.py:

1. Add all the translation functions from this file to the top of receipt_ocr.py:
   - translate_swedish_to_english()
   - _translate_with_google_api()
   - _translate_with_dictionary()
   - extract_with_translation()

2. REPLACE the existing receipt_upload_ui() function with:
   receipt_upload_ui_with_translation()
   
3. Update the import in Main_Dashboard_App.py:
   from receipt_ocr import receipt_upload_ui_with_translation as receipt_upload_ui

OR

1. Simply add these functions to receipt_ocr.py
2. Modify the existing receipt_upload_ui() to call extract_with_translation()
   instead of extract_text_from_image()
"""