# utils.py
def calculate_price_per_unit(price, qty):
    try:
        qty = float(qty)
    except Exception:
        qty = 0.0
    if qty == 0:
        return 0.0
    return round(float(price) / qty, 2)
