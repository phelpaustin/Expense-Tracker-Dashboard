# ux_components.py
"""
Enhanced UX components for better user experience.
Includes progress indicators, confirmations, tooltips, and smart defaults.
"""
import streamlit as st
import pandas as pd
from typing import Callable, Optional, Any, List
from datetime import datetime
import time


# ============================================================
# CONFIRMATION DIALOGS
# ============================================================
def confirm_action(
    message: str,
    confirm_label: str = "✅ Confirm",
    cancel_label: str = "❌ Cancel",
    danger: bool = False
) -> bool:
    """
    Show confirmation dialog for destructive actions.
    
    Args:
        message: Confirmation message
        confirm_label: Label for confirm button
        cancel_label: Label for cancel button
        danger: If True, shows as dangerous action
    
    Returns:
        True if confirmed, False otherwise
    """
    st.warning(f"⚠️ {message}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        confirmed = st.button(
            confirm_label,
            type="primary" if not danger else "secondary",
            width="stretch"
        )
    
    with col2:
        cancelled = st.button(
            cancel_label,
            width="stretch"
        )
    
    if cancelled:
        st.info("Action cancelled")
        return False
    
    return confirmed


def confirm_delete(item_name: str, count: int = 1) -> bool:
    """
    Specific confirmation for delete actions.
    
    Args:
        item_name: Name of item(s) being deleted
        count: Number of items
    
    Returns:
        True if confirmed
    """
    if count == 1:
        message = f"Delete {item_name}? This cannot be undone."
    else:
        message = f"Delete {count} {item_name}? This cannot be undone."
    
    return confirm_action(
        message,
        confirm_label="🗑️ Delete",
        cancel_label="❌ Keep",
        danger=True
    )


# ============================================================
# PROGRESS INDICATORS
# ============================================================
class ProgressTracker:
    """Track and display progress for long operations."""
    
    def __init__(self, total_steps: int, description: str = "Processing"):
        """
        Args:
            total_steps: Total number of steps
            description: Operation description
        """
        self.total_steps = total_steps
        self.current_step = 0
        self.description = description
        self.progress_bar = st.progress(0)
        self.status_text = st.empty()
        self.start_time = time.time()
    
    def update(self, step: int, message: Optional[str] = None):
        """Update progress."""
        self.current_step = step
        progress = min(step / self.total_steps, 1.0)
        self.progress_bar.progress(progress)
        
        # Calculate ETA
        elapsed = time.time() - self.start_time
        if step > 0:
            eta = (elapsed / step) * (self.total_steps - step)
            eta_str = f" (ETA: {eta:.0f}s)" if eta > 1 else ""
        else:
            eta_str = ""
        
        status_msg = message or f"{self.description} {step}/{self.total_steps}{eta_str}"
        self.status_text.text(status_msg)
    
    def complete(self, message: str = "Complete!"):
        """Mark as complete and clean up."""
        self.progress_bar.progress(1.0)
        self.status_text.success(f"✅ {message}")
        time.sleep(1)
        self.progress_bar.empty()
        self.status_text.empty()
    
    def error(self, message: str = "Failed"):
        """Mark as failed and clean up."""
        self.status_text.error(f"❌ {message}")
        self.progress_bar.empty()


def show_spinner_with_message(message: str, success_message: Optional[str] = None):
    """
    Context manager for spinner with success message.
    
    Usage:
        with show_spinner_with_message("Loading data", "Data loaded!"):
            df = load_data()
    """
    class SpinnerContext:
        def __init__(self, msg, success_msg):
            self.msg = msg
            self.success_msg = success_msg
            self.spinner = None
        
        def __enter__(self):
            self.spinner = st.spinner(self.msg)
            self.spinner.__enter__()
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            self.spinner.__exit__(exc_type, exc_val, exc_tb)
            if exc_type is None and self.success_msg:
                st.success(self.success_msg)
    
    return SpinnerContext(message, success_message)


# ============================================================
# TOOLTIPS & HELP
# ============================================================
def show_tooltip(label: str, help_text: str):
    """Display label with tooltip."""
    st.markdown(f"**{label}** ℹ️")
    with st.expander("More info"):
        st.info(help_text)


def contextual_help(context: str):
    """Show contextual help for different features."""
    help_content = {
        "add_expense": """
        ### Adding Expenses
        
        1. Select the date of purchase
        2. Choose expense type (Goods/Service)
        3. Select shop and currency
        4. Add multiple items:
           - Enter item name (required)
           - Specify quantity and unit
           - Enter amount in selected currency
        5. Click "Add All Expenses" to save
        
        **Tips:**
        - You can add multiple items from same shopping trip
        - Currency is automatically converted to SEK
        - Clear items to start over
        """,
        
        "filters": """
        ### Using Filters
        
        - **Category**: Filter by expense category
        - **Shop**: Filter by store/shop
        - **Price Range**: Use slider to filter by amount
        - **Date Range**: Select time period
        
        **Tips:**
        - Multiple selections act as AND filters
        - Clear filters to see all data
        - Filters apply to all charts
        """,
        
        "import": """
        ### Importing Data
        
        Supported formats: CSV, XLSX
        
        Required columns:
        - Date
        - ExpenseType
        - Item
        - PricePaid
        - Quantity
        
        **Tips:**
        - Preview and edit data before importing
        - Fix validation errors before merging
        - Backup your data before large imports
        """
    }
    
    if context in help_content:
        with st.expander("ℹ️ Help", expanded=False):
            st.markdown(help_content[context])


# ============================================================
# SMART DEFAULTS
# ============================================================
class SmartDefaults:
    """Provide smart default values based on user history."""
    
    @staticmethod
    def get_last_used_shop(df: pd.DataFrame, category: Optional[str] = None) -> Optional[str]:
        """Get the most recently used shop (optionally for a category)."""
        if df.empty:
            return None
        
        # Filter by category if provided
        if category:
            df = df[df["Category"] == category]
        
        if df.empty:
            return None
        
        # Get most recent shop
        df_sorted = df.sort_values("Date", ascending=False)
        return df_sorted.iloc[0]["Shop"]
    
    @staticmethod
    def get_common_items(df: pd.DataFrame, category: str, top_n: int = 5) -> List[str]:
        """Get commonly purchased items in a category."""
        if df.empty:
            return []
        
        category_df = df[df["Category"] == category]
        if category_df.empty:
            return []
        
        # Count item frequency
        item_counts = category_df["Item"].value_counts()
        return item_counts.head(top_n).index.tolist()
    
    @staticmethod
    def suggest_quantity(df: pd.DataFrame, item: str) -> Optional[float]:
        """Suggest typical quantity for an item."""
        if df.empty:
            return None
        
        item_df = df[df["Item"] == item]
        if item_df.empty:
            return None
        
        # Return median quantity
        return item_df["Quantity"].median()
    
    @staticmethod
    def suggest_price(df: pd.DataFrame, item: str, shop: Optional[str] = None) -> Optional[float]:
        """Suggest typical price for an item."""
        if df.empty:
            return None
        
        item_df = df[df["Item"] == item]
        
        # Filter by shop if provided
        if shop:
            shop_df = item_df[item_df["Shop"] == shop]
            if not shop_df.empty:
                item_df = shop_df
        
        if item_df.empty:
            return None
        
        # Return median price
        return item_df["PricePaid"].median()


# ============================================================
# AUTO-SUGGESTIONS
# ============================================================
def autocomplete_input(
    label: str,
    suggestions: List[str],
    key: str,
    placeholder: str = "Start typing...",
    allow_custom: bool = True
) -> str:
    """
    Input with autocomplete suggestions.
    
    Args:
        label: Input label
        suggestions: List of suggestions
        key: Unique key
        placeholder: Placeholder text
        allow_custom: Allow custom values not in suggestions
    
    Returns:
        Selected or entered value
    """
    # Show suggestions in a selectbox if available
    if suggestions:
        col1, col2 = st.columns([3, 1])
        
        with col1:
            if allow_custom:
                value = st.text_input(label, placeholder=placeholder, key=key)
            else:
                value = st.selectbox(label, [""] + suggestions, key=key)
        
        with col2:
            if st.button("💡 Suggestions", key=f"{key}_suggest"):
                st.info("Common choices: " + ", ".join(suggestions[:5]))
        
        return value
    else:
        return st.text_input(label, placeholder=placeholder, key=key)


# ============================================================
# BULK ACTIONS
# ============================================================
def bulk_action_selector(df: pd.DataFrame, action_name: str = "Process") -> tuple:
    """
    Select rows for bulk actions.
    
    Args:
        df: DataFrame to select from
        action_name: Name of action
    
    Returns:
        Tuple of (selected_indices, action_confirmed)
    """
    if df.empty:
        st.info("No data available")
        return [], False
    
    st.markdown(f"### Select items to {action_name.lower()}")
    
    # Show selectable dataframe
    selection = st.multiselect(
        "Select rows by index",
        options=df.index.tolist(),
        format_func=lambda x: f"Row {x}: {df.loc[x, 'Item']}" if 'Item' in df.columns else f"Row {x}"
    )
    
    if selection:
        st.dataframe(df.loc[selection], width="stretch")
        
        if st.button(f"{action_name} {len(selection)} items", type="primary"):
            return selection, True
    
    return selection, False


# ============================================================
# FEEDBACK & NOTIFICATIONS
# ============================================================
class NotificationManager:
    """Manage user notifications."""
    
    @staticmethod
    def show_success(message: str, auto_dismiss: bool = True):
        """Show success notification."""
        placeholder = st.empty()
        placeholder.success(f"✅ {message}")
        
        if auto_dismiss:
            time.sleep(3)
            placeholder.empty()
    
    @staticmethod
    def show_error(message: str, details: Optional[str] = None):
        """Show error notification with optional details."""
        st.error(f"❌ {message}")
        
        if details:
            with st.expander("🔍 Error details"):
                st.code(details)
    
    @staticmethod
    def show_warning(message: str, action: Optional[Callable] = None, action_label: str = "Fix"):
        """Show warning with optional action button."""
        st.warning(f"⚠️ {message}")
        
        if action:
            if st.button(action_label):
                action()
    
    @staticmethod
    def show_info(message: str, dismissible: bool = True):
        """Show info notification."""
        if dismissible:
            with st.expander("ℹ️ Information"):
                st.info(message)
        else:
            st.info(f"ℹ️ {message}")


# ============================================================
# KEYBOARD SHORTCUTS
# ============================================================
def show_keyboard_shortcuts():
    """Display keyboard shortcuts help."""
    with st.expander("⌨️ Keyboard Shortcuts"):
        st.markdown("""
        | Shortcut | Action |
        |----------|--------|
        | `Ctrl+S` | Save changes |
        | `Ctrl+F` | Focus on filter |
        | `Esc` | Close dialog |
        | `Tab` | Next field |
        | `Shift+Tab` | Previous field |
        
        **Tip:** Use Tab to navigate between fields quickly
        """)


# ============================================================
# EMPTY STATES
# ============================================================
def show_empty_state(
    title: str,
    description: str,
    action_label: Optional[str] = None,
    action: Optional[Callable] = None,
    icon: str = "📭"
):
    """
    Show empty state with call-to-action.
    
    Args:
        title: Empty state title
        description: Description text
        action_label: Label for action button
        action: Function to call when button clicked
        icon: Emoji icon
    """
    st.markdown(f"<div style='text-align: center; padding: 3rem;'>", unsafe_allow_html=True)
    st.markdown(f"# {icon}")
    st.markdown(f"### {title}")
    st.markdown(description)
    
    if action_label and action:
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button(action_label, type="primary", width="stretch"):
                action()
    
    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# ONBOARDING
# ============================================================
def show_onboarding_tour():
    """Show onboarding tour for first-time users."""
    if "onboarding_completed" not in st.session_state:
        st.session_state.onboarding_completed = False
    
    if not st.session_state.onboarding_completed:
        with st.expander("👋 Welcome! Take a quick tour", expanded=True):
            st.markdown("""
            ### Welcome to Expense Tracker! 
            
            Here's how to get started:
            
            1. **➕ Add Expense**: Click to add your first expense
            2. **🔍 Filters**: Use sidebar filters to view specific data
            3. **📊 Analytics**: View spending trends and insights
            4. **📥 Import**: Bulk import from CSV/Excel
            
            **Tip:** Start by adding a few expenses to see the charts in action!
            """)
            
            if st.button("Got it! ✅", type="primary"):
                st.session_state.onboarding_completed = True
                st.rerun()


# ============================================================
# EXPORT
# ============================================================
__all__ = [
    # Confirmations
    "confirm_action",
    "confirm_delete",
    
    # Progress
    "ProgressTracker",
    "show_spinner_with_message",
    
    # Help
    "show_tooltip",
    "contextual_help",
    
    # Smart defaults
    "SmartDefaults",
    
    # Autocomplete
    "autocomplete_input",
    
    # Bulk actions
    "bulk_action_selector",
    
    # Notifications
    "NotificationManager",
    
    # Shortcuts
    "show_keyboard_shortcuts",
    
    # Empty states
    "show_empty_state",
    
    # Onboarding
    "show_onboarding_tour",
]