import pandas as pd
import json
import os

# Resolve paths relative to the project root (one level up from scripts/)
# so the script works regardless of the current working directory.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---- Config ----
EXCEL_FILE = os.path.join(_ROOT, "expenses_export.xlsx")  # your file
OUTPUT_FILE = os.path.join(_ROOT, "data", "dropdown_options.json")


def build_dropdown_from_excel(file_path):
    # Load Excel
    df = pd.read_excel(file_path)

    # Normalize column names
    df.columns = df.columns.str.strip().str.lower()

    # Map your actual columns to expected names
    column_map = {
        "category": "category",
        "subcategory": "subcategory",
        "shop": "shop",
        "quantityunit": "unit"
    }

    # Check required columns exist
    missing = [col for col in column_map if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in Excel: {missing}")

    # Rename columns to friendly names
    df = df.rename(columns={
        "quantityunit": "unit"
    })

    # Extract categories
    categories = sorted(df["category"].dropna().unique().tolist())

    # Extract subcategories grouped by category
    subcategories = {}
    for cat in categories:
        subs = (
            df[df["category"] == cat]["subcategory"]
            .dropna()
            .unique()
            .tolist()
        )
        subcategories[cat] = sorted(subs)

    # Extract shops
    shops = sorted(df["shop"].dropna().unique().tolist())

    # Extract units
    units = sorted(df["unit"].dropna().unique().tolist())

    return {
        "categories": categories,
        "subcategories": subcategories,
        "shops": shops,
        "units": units
    }


def save_json(data, output_path):
    # Ensure folder exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(data, f, indent=4)

    print(f"Saved JSON → {output_path}")


def main():
    dropdown_data = build_dropdown_from_excel(EXCEL_FILE)
    save_json(dropdown_data, OUTPUT_FILE)
    print("dropdown_options.json generated successfully!")


if __name__ == "__main__":
    main()
