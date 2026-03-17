# feature_flags.py
# ──────────────────────────────────────────────────────────────
#  Optional-module feature flags — all normalised to HAS_ prefix.
#
#  Previously the codebase mixed HAS_ and _USE_ prefixes.  Every
#  flag is now HAS_<MODULE> for consistency and grep-ability.
#  Import stubs are also collected here so Main_Dashboard_App.py
#  and the page modules only ever import symbols — not try/except
#  blocks — for optional features.
# ──────────────────────────────────────────────────────────────

# ── Spending Intelligence ──────────────────────────────────────
try:
    from spending_intelligence import (           # noqa: F401
        hotspot_analysis, temporal_patterns,
        budget_intelligence, savings_opportunities, smart_kpi_row,
    )
    HAS_INTELLIGENCE = True
except ImportError:
    HAS_INTELLIGENCE = False
    hotspot_analysis = temporal_patterns = budget_intelligence = None
    savings_opportunities = smart_kpi_row = None

# ── Import workflow (was _USE_IMPORT_WORKFLOW / HAS_MERGE_FN) ──
try:
    from import_export import import_workflow     # noqa: F401
    HAS_IMPORT_WORKFLOW = True
except ImportError:
    HAS_IMPORT_WORKFLOW = False
    import_workflow = None

try:
    from import_export import perform_merge_if_ready  # noqa: F401
    HAS_MERGE = True                             # ← was HAS_MERGE_FN
except ImportError:
    HAS_MERGE = False
    perform_merge_if_ready = None

try:
    from import_export import import_button, export_buttons  # noqa: F401
except ImportError:
    import_button = export_buttons = None

# ── Budget ─────────────────────────────────────────────────────
try:
    from budget_manager import budget_dashboard_ui, budget_setup_ui, load_budgets  # noqa: F401
    HAS_BUDGET = True
except ImportError:
    HAS_BUDGET = False
    budget_dashboard_ui = budget_setup_ui = None
    def load_budgets(): return {}

# ── Recurring ──────────────────────────────────────────────────
try:
    from recurring_manager import recurring_manager_ui  # noqa: F401
    HAS_RECURRING = True
except ImportError:
    HAS_RECURRING = False
    recurring_manager_ui = None

# ── Advanced analytics ─────────────────────────────────────────
try:
    from analytics_advanced import (              # noqa: F401
        yoy_comparison_chart, mom_comparison_chart,
        spending_forecast_chart, anomaly_detection_chart,
        spending_insights, category_evolution_chart, daily_heatmap,
    )
    HAS_ADVANCED = True
except ImportError:
    HAS_ADVANCED = False
    yoy_comparison_chart = mom_comparison_chart = spending_forecast_chart = None
    anomaly_detection_chart = spending_insights = category_evolution_chart = daily_heatmap = None

# ── ML categoriser ─────────────────────────────────────────────
try:
    from ml_categorizer import smart_categorize_ui  # noqa: F401
    HAS_ML = True
except ImportError:
    HAS_ML = False
    smart_categorize_ui = None

# ── Receipt OCR ────────────────────────────────────────────────
try:
    from receipt_ocr import receipt_upload_ui_with_translation  # noqa: F401
    HAS_OCR = True
except ImportError:
    HAS_OCR = False
    receipt_upload_ui_with_translation = None

# ── Tax export ─────────────────────────────────────────────────
try:
    from tax_export import tax_export_ui         # noqa: F401
    HAS_TAX = True
except ImportError:
    HAS_TAX = False
    tax_export_ui = None

# ── Backup ─────────────────────────────────────────────────────
try:
    from backup_manager import backup_settings_ui  # noqa: F401
    HAS_BACKUP = True
except ImportError:
    HAS_BACKUP = False
    backup_settings_ui = None

# ── Notifications ──────────────────────────────────────────────
try:
    from notification_manager import render_notification_banner, notification_settings_ui  # noqa: F401
    HAS_NOTIFY = True
except ImportError:
    HAS_NOTIFY = False
    render_notification_banner = notification_settings_ui = None

# ── Multi-user ─────────────────────────────────────────────────
try:
    from multi_user_manager import (              # noqa: F401
        user_switcher_widget, user_management_ui,
        user_splits_ui, filter_by_user,
    )
    HAS_USERS = True
except ImportError:
    HAS_USERS = False
    user_switcher_widget = user_management_ui = user_splits_ui = None
    def filter_by_user(df, user_id=None): return df

# ── Price tracker ──────────────────────────────────────────────
try:
    from price_tracker import price_tracker_ui   # noqa: F401
    HAS_PRICE_TRACKER = True
except ImportError:
    HAS_PRICE_TRACKER = False
    price_tracker_ui = None

# ── Financial metrics ──────────────────────────────────────────
try:
    from financial_metrics import financial_metrics_ui  # noqa: F401
    HAS_FINANCIAL_METRICS = True
except ImportError:
    HAS_FINANCIAL_METRICS = False
    financial_metrics_ui = None
