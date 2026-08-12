# ml_categorizer.py
"""
Smart expense categorization using keyword rules + optional ML (sklearn).
Falls back gracefully to rule-based matching if sklearn not installed.
"""
import re
import json
import pandas as pd
import streamlit as st
from pathlib import Path
from typing import Optional
from config import Columns


RULES_FILE = "data/categorization_rules.json"
from json_store import JsonStore
_RULES_STORE = JsonStore(RULES_FILE, default={}, sync=False)


# ============================================================
# BUILT-IN KEYWORD RULES
# ============================================================
DEFAULT_RULES = {
    "Groceries": [
        "milk", "bread", "eggs", "butter", "cheese", "yogurt", "flour", "sugar",
        "rice", "pasta", "vegetables", "fruits", "meat", "chicken", "fish",
        "ica", "lidl", "coop", "willys", "hemköp", "citygross", "netto",
        "juice", "coffee", "tea", "cereal", "snacks", "chocolate"
    ],
    "Transport": [
        "bus", "train", "metro", "subway", "taxi", "uber", "lyft", "fuel",
        "petrol", "gas", "parking", "toll", "ferry", "sl", "flight", "airline",
        "tram", "bike", "cycling", "car", "vehicle", "commute"
    ],
    "Dining": [
        "restaurant", "cafe", "coffee", "pizza", "sushi", "burger", "mcdonalds",
        "starbucks", "mcafe", "subway", "kebab", "lunch", "dinner", "breakfast",
        "bistro", "bar", "pub", "takeaway", "delivery", "foodora", "wolt"
    ],
    "Entertainment": [
        "netflix", "spotify", "steam", "cinema", "movie", "concert", "ticket",
        "disney", "hbo", "amazon prime", "youtube", "game", "gaming", "museum",
        "theatre", "bowling", "gym", "fitness", "yoga", "sport"
    ],
    "Healthcare": [
        "pharmacy", "doctor", "dentist", "hospital", "medicine", "prescription",
        "apoteket", "apotek", "clinic", "health", "optical", "glasses",
        "vitamin", "supplement"
    ],
    "Utilities": [
        "electricity", "water", "gas", "internet", "phone", "mobile", "broadband",
        "heating", "insurance", "rent", "landlord", "tele2", "telia", "telenor",
        "wifi", "cable"
    ],
    "Shopping": [
        "h&m", "zara", "ikea", "elgiganten", "mediamarkt", "amazon", "ebay",
        "clothes", "shoes", "jacket", "dress", "shirt", "pants", "electronics",
        "laptop", "phone", "charger", "furniture", "decor"
    ],
    "Education": [
        "book", "course", "udemy", "coursera", "school", "university", "tutoring",
        "library", "kindle", "textbook", "workshop", "seminar", "training"
    ],
    "Travel": [
        "hotel", "airbnb", "hostel", "booking.com", "expedia", "trip", "holiday",
        "vacation", "airport", "luggage", "suitcase", "travel insurance"
    ],
    "Personal Care": [
        "haircut", "salon", "barber", "cosmetics", "shampoo", "soap", "skincare",
        "makeup", "perfume", "beauty", "spa", "nail"
    ],
}


# ============================================================
# RULE MANAGEMENT
# ============================================================
def load_custom_rules() -> dict:
    return _RULES_STORE.load()


def save_custom_rules(rules: dict):
    _RULES_STORE.save(rules)


def get_all_rules() -> dict:
    merged = {k: list(v) for k, v in DEFAULT_RULES.items()}
    custom = load_custom_rules()
    for cat, keywords in custom.items():
        if cat in merged:
            merged[cat] = list(set(merged[cat] + keywords))
        else:
            merged[cat] = keywords
    return merged


# ============================================================
# RULE-BASED CATEGORIZATION
# ============================================================
def categorize_by_rules(item: str, shop: str = "") -> Optional[str]:
    """Match item/shop against keyword rules."""
    text = f"{item} {shop}".lower().strip()
    rules = get_all_rules()
    scores = {}
    for category, keywords in rules.items():
        score = sum(1 for kw in keywords if kw.lower() in text)
        if score > 0:
            scores[category] = score
    if scores:
        return max(scores, key=scores.get)
    return None


# ============================================================
# ML-BASED CATEGORIZATION
# ============================================================
class MLCategorizer:
    """Optional ML-based categorizer using sklearn."""
    
    def __init__(self):
        self.model = None
        self.vectorizer = None
        self.label_encoder = None
        self.is_trained = False
    
    def train(self, df: pd.DataFrame) -> bool:
        """Train on historical labeled data."""
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.naive_bayes import MultinomialNB
            from sklearn.preprocessing import LabelEncoder

            if df.empty or Columns.CATEGORY not in df.columns:
                return False

            labeled = df.dropna(subset=[Columns.CATEGORY, Columns.ITEM])
            if len(labeled) < 10:
                return False

            texts = (labeled[Columns.ITEM].fillna("") + " " + labeled.get(Columns.SHOP, pd.Series("", index=labeled.index)).fillna("")).str.lower()
            labels = labeled[Columns.CATEGORY]

            self.label_encoder = LabelEncoder()
            y = self.label_encoder.fit_transform(labels)

            self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), max_features=500)
            X = self.vectorizer.fit_transform(texts)

            self.model = MultinomialNB()
            self.model.fit(X, y)
            self.is_trained = True
            return True

        except ImportError:
            return False
        except Exception:
            return False
    
    def predict(self, item: str, shop: str = "") -> Optional[str]:
        """Predict category for a new item."""
        if not self.is_trained:
            return None
        try:
            text = f"{item} {shop}".lower()
            X = self.vectorizer.transform([text])
            y = self.model.predict(X)
            return self.label_encoder.inverse_transform(y)[0]
        except Exception:
            return None
    
    def predict_with_confidence(self, item: str, shop: str = "") -> tuple:
        """Return (category, confidence_score)."""
        if not self.is_trained:
            return None, 0.0
        try:
            text = f"{item} {shop}".lower()
            X = self.vectorizer.transform([text])
            proba = self.model.predict_proba(X)[0]
            best_idx = proba.argmax()
            confidence = float(proba[best_idx])
            category = self.label_encoder.inverse_transform([best_idx])[0]
            return category, confidence
        except Exception:
            return None, 0.0


# Global ML instance
_ml_categorizer = MLCategorizer()


def get_suggestion(item: str, shop: str = "", df: Optional[pd.DataFrame] = None, confidence_threshold: float = 0.6) -> dict:
    """
    Get category suggestion using ML + rule fallback.
    
    Returns:
        dict with 'category', 'confidence', 'method'
    """
    # Try ML first
    if df is not None and not _ml_categorizer.is_trained:
        _ml_categorizer.train(df)

    if _ml_categorizer.is_trained:
        cat, conf = _ml_categorizer.predict_with_confidence(item, shop)
        if cat and conf >= confidence_threshold:
            return {"category": cat, "confidence": conf, "method": "ml"}

    # Fall back to rules
    cat = categorize_by_rules(item, shop)
    if cat:
        return {"category": cat, "confidence": 0.7, "method": "rules"}

    return {"category": None, "confidence": 0.0, "method": "none"}


def auto_categorize_dataframe(df: pd.DataFrame, overwrite_existing: bool = False) -> pd.DataFrame:
    """Auto-categorize rows with missing or empty categories."""
    df2 = df.copy()
    changed = 0

    # Vectorised pre-filter: only rows that actually need a category are
    # visited, instead of iterating (and calling the model for) every row.
    if overwrite_existing or Columns.CATEGORY not in df2.columns:
        needs = pd.Series(True, index=df2.index)
    else:
        cat = df2[Columns.CATEGORY]
        needs = cat.isna() | (cat.astype(str).str.strip() == "")

    has_item = Columns.ITEM in df2.columns
    has_shop = Columns.SHOP in df2.columns
    for idx in df2.index[needs]:
        suggestion = get_suggestion(
            str(df2.at[idx, Columns.ITEM]) if has_item else "",
            str(df2.at[idx, Columns.SHOP]) if has_shop else "",
            df,
        )
        if suggestion["category"]:
            df2.at[idx, Columns.CATEGORY] = suggestion["category"]
            changed += 1
    return df2, changed


# ============================================================
# UI
# ============================================================
def smart_categorize_ui(df: pd.DataFrame, save_fn, sheet=None):
    st.markdown("## 🤖 Smart Categorization")

    # Train model
    trained = _ml_categorizer.train(df)
    method_label = "ML + Rules" if trained else "Rules Only"
    st.info(f"🧠 Categorization engine: **{method_label}** (trained on {len(df)} expenses)")

    # Live suggestion
    st.markdown("### 🔍 Test Categorizer")
    c1, c2 = st.columns(2)
    test_item = c1.text_input("Item name", placeholder="e.g., Milk, Netflix, Bus")
    test_shop = c2.text_input("Shop/Provider", placeholder="e.g., ICA, SL")
    if test_item:
        result = get_suggestion(test_item, test_shop, df)
        if result["category"]:
            st.success(f"**Suggested:** {result['category']} (Confidence: {result['confidence']:.0%}, Method: {result['method']})")
        else:
            st.warning("No suggestion found. You can add a keyword rule below.")

    # Auto-categorize uncategorized rows
    st.markdown("### ⚡ Auto-Categorize Missing")
    uncategorized = df[df[Columns.CATEGORY].isna() | (df[Columns.CATEGORY] == "") | (df[Columns.CATEGORY] == "Uncategorized")] if not df.empty else pd.DataFrame()
    st.metric("Rows without category", len(uncategorized))

    if not uncategorized.empty:
        if st.button(f"🤖 Auto-Categorize {len(uncategorized)} Rows", type="primary"):
            with st.spinner("Categorizing..."):
                df_updated, changed = auto_categorize_dataframe(df)
            save_fn(df_updated, sheet)
            st.success(f"✅ Categorized {changed} rows")
            st.rerun()

    # Manage custom rules
    st.markdown("### 📚 Manage Keyword Rules")
    all_rules = get_all_rules()
    cats = sorted(all_rules.keys())
    selected_cat = st.selectbox("Category", cats, key="rule_cat_select")
    if selected_cat:
        st.markdown(f"**Current keywords for {selected_cat}:**")
        st.code(", ".join(sorted(all_rules[selected_cat][:20])) + (" ..." if len(all_rules[selected_cat]) > 20 else ""))

    with st.form("add_rule_form"):
        c1, c2 = st.columns(2)
        new_cat = c1.text_input("Category")
        new_keywords = c2.text_input("Keywords (comma-separated)", placeholder="milk, dairy, cream")
        if st.form_submit_button("Add Rule"):
            if new_cat.strip() and new_keywords.strip():
                custom = load_custom_rules()
                kws = [k.strip().lower() for k in new_keywords.split(",") if k.strip()]
                custom.setdefault(new_cat.strip(), [])
                custom[new_cat.strip()] = list(set(custom[new_cat.strip()] + kws))
                save_custom_rules(custom)
                st.success(f"✅ Added {len(kws)} keyword(s) to {new_cat}")
                st.rerun()
