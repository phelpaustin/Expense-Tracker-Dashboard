# import_export.py
import streamlit as st
import pandas as pd
from io import BytesIO
from config import ImportState, ImportStateManager
from validators import ExpenseValidator


# ============================================================
# 📥 Import Expense Data (CSV / XLSX) - REFACTORED
# ============================================================
def import_workflow(existing_columns=None):
    """
    Manages the complete import workflow using state machine.
    
    Args:
        existing_columns: List of expected column names
    
    Returns:
        None (manages state internally)
    """
    st.sidebar.markdown("---")
    st.sidebar.subheader("📥 Import Data")
    
    # Get current state
    current_state = ImportStateManager.get_state()
    
    # Show status indicator
    _show_status_indicator(current_state)
    
    # State: IDLE or ERROR - Show file uploader
    if ImportStateManager.can_show_upload_ui():
        _handle_file_upload(existing_columns)
    
    # State: FILE_UPLOADED or EDITING - Show preview with edit
    elif ImportStateManager.should_show_preview():
        _handle_preview_and_edit()
    
    # State: COMPLETED - Show success message
    elif current_state == ImportState.COMPLETED:
        _handle_completion()


def _show_status_indicator(state: ImportState):
    """Display current import status."""
    status_messages = {
        ImportState.IDLE: ("ℹ️", "Ready to import", "info"),
        ImportState.FILE_UPLOADED: ("📄", "File uploaded - review below", "info"),
        ImportState.EDITING: ("✏️", "Editing imported data", "info"),
        ImportState.CONFIRMED: ("⏳", "Merging data...", "warning"),
        ImportState.MERGING: ("⏳", "Merge in progress...", "warning"),
        ImportState.COMPLETED: ("✅", ImportStateManager.get_success_message() or "Import completed!", "success"),
        ImportState.ERROR: ("❌", ImportStateManager.get_error() or "Import failed", "error"),
    }
    
    if state in status_messages:
        icon, message, msg_type = status_messages[state]
        
        if msg_type == "success":
            st.sidebar.success(f"{icon} {message}")
        elif msg_type == "error":
            st.sidebar.error(f"{icon} {message}")
        elif msg_type == "warning":
            st.sidebar.warning(f"{icon} {message}")
        else:
            st.sidebar.info(f"{icon} {message}")


def _handle_file_upload(existing_columns):
    """Handle initial file upload."""
    # Show error if previous attempt failed
    error = ImportStateManager.get_error()
    if error:
        st.sidebar.error(f"Previous import failed: {error}")
        if st.sidebar.button("🔄 Try Again"):
            ImportStateManager.reset()
            st.rerun()
    
    # File uploader
    uploaded_file = st.sidebar.file_uploader(
        "Upload a CSV or Excel file",
        type=["csv", "xlsx"],
        key="import_file_uploader"
    )
    
    if not uploaded_file:
        return
    
    # Read file
    try:
        if uploaded_file.name.endswith(".csv"):
            df_import = pd.read_csv(uploaded_file)
        else:
            df_import = pd.read_excel(uploaded_file)
    except Exception as e:
        ImportStateManager.set_state(
            ImportState.ERROR,
            f"Failed to read file: {str(e)}"
        )
        st.rerun()
        return
    
    # Validate file is not empty
    if df_import.empty:
        ImportStateManager.set_state(
            ImportState.ERROR,
            "Uploaded file is empty"
        )
        st.rerun()
        return
    
    # Prepare columns
    expected_cols = existing_columns or [
        "Date", "ExpenseType", "Category", "Subcategory", "Item", "Brand",
        "Shop", "PricePaid", "Currency", "Quantity", "QuantityUnit", "PricePerUnit"
    ]
    
    for col in expected_cols:
        if col not in df_import.columns:
            df_import[col] = None
    
    df_import = df_import[expected_cols]
    
    # Normalize dates
    if "Date" in df_import.columns:
        df_import["Date"] = pd.to_datetime(df_import["Date"], errors="coerce").dt.date
    
    # ============ VALIDATE IMPORTED DATA ============
    is_valid, errors, stats = ExpenseValidator.validate_import_data(df_import)
    
    # Show validation results
    if not is_valid:
        st.sidebar.warning(f"⚠️ Validation issues found in {stats['invalid_rows']} rows")
    else:
        st.sidebar.success(f"✅ All {stats['total_rows']} rows are valid")
    
    # Store data and update state (even if validation failed - user can fix)
    ImportStateManager.set_pending_data(df_import)
    ImportStateManager.set_state(ImportState.FILE_UPLOADED)
    
    st.sidebar.info(f"📊 Loaded {len(df_import)} rows for review")
    st.rerun()


def _handle_preview_and_edit():
    """Handle preview and editing of imported data."""
    pending_df = ImportStateManager.get_pending_data()
    
    if pending_df is None or pending_df.empty:
        ImportStateManager.set_state(
            ImportState.ERROR,
            "No data to preview"
        )
        st.rerun()
        return
    
    # Show preview section in main area (not sidebar)
    st.markdown("---")
    st.subheader("📄 Preview Imported Data")
    
    # ============ VALIDATION SUMMARY ============
    is_valid, errors, invalid_df = ExpenseValidator.validate_dataframe(pending_df)
    
    if is_valid:
        st.success(f"✅ All {len(pending_df)} rows passed validation!")
    else:
        st.warning(f"⚠️ Found validation issues in {len(invalid_df)} rows")
        
        with st.expander("🔍 View Validation Errors", expanded=True):
            # Show first 10 errors
            for i, error in enumerate(errors[:10]):
                st.error(error)
            
            if len(errors) > 10:
                st.info(f"... and {len(errors) - 10} more errors")
            
            # Show invalid rows
            if not invalid_df.empty:
                st.markdown("**Invalid rows (fix before merging):**")
                st.dataframe(invalid_df, width="stretch", hide_index=True)
    
    st.info(f"**{len(pending_df)} rows** loaded. Review and edit if needed before merging.")
    
    # Editable data
    edited_df = st.data_editor(
        pending_df,
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        key="import_data_editor"
    )
    
    # Update state to EDITING if user made changes
    if not edited_df.equals(pending_df):
        ImportStateManager.set_pending_data(edited_df)
        ImportStateManager.set_state(ImportState.EDITING)
    
    # Action buttons
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        if st.button("❌ Cancel Import", width="stretch"):
            ImportStateManager.reset()
            st.rerun()
    
    with col2:
        if st.button("🔄 Reset to Original", width="stretch"):
            # Reset to originally uploaded data
            ImportStateManager.set_state(ImportState.FILE_UPLOADED)
            st.rerun()
    
    with col3:
        # Only allow merge if data is valid
        if is_valid:
            if st.button("✅ Confirm & Merge", type="primary", width="stretch"):
                # Move to confirmed state
                ImportStateManager.set_pending_data(edited_df)
                ImportStateManager.set_state(ImportState.CONFIRMED)
                st.rerun()
        else:
            st.button(
                "⚠️ Fix Errors First", 
                width="stretch", 
                disabled=True,
                help="Cannot merge - please fix validation errors first"
            )


def _handle_completion():
    """Handle completed import state."""
    success_msg = ImportStateManager.get_success_message()
    if success_msg:
        st.sidebar.success(success_msg)
    
    # Provide option to import another file
    if st.sidebar.button("📥 Import Another File"):
        ImportStateManager.reset()
        st.rerun()


# ============================================================
# 🔄 Merge Handler (Called from Main App)
# ============================================================
def perform_merge_if_ready(df_existing, save_fn, sheet=None):
    """
    Check if merge is ready and perform it.
    
    This should be called from the main app after data is loaded.
    
    Args:
        df_existing: Existing DataFrame to merge into
        save_fn: Function to save merged data
        sheet: Google Sheet object (if applicable)
    
    Returns:
        tuple: (merged_df, merge_performed)
    """
    if not ImportStateManager.is_ready_to_merge():
        return df_existing, False
    
    pending_df = ImportStateManager.get_pending_data()
    
    if pending_df is None or pending_df.empty:
        ImportStateManager.set_state(
            ImportState.ERROR,
            "No data to merge"
        )
        return df_existing, False
    
    try:
        # Update state to MERGING
        ImportStateManager.set_state(ImportState.MERGING)
        
        # ============ FINAL VALIDATION BEFORE MERGE ============
        is_valid, errors, invalid_df = ExpenseValidator.validate_dataframe(pending_df)
        
        if not is_valid:
            error_msg = f"Cannot merge: {len(invalid_df)} invalid rows. " + errors[0] if errors else "Validation failed"
            ImportStateManager.set_state(ImportState.ERROR, error_msg)
            return df_existing, False
        
        # Import clean_data if available
        from data_manager import clean_data
        
        # Perform merge
        df_combined = pd.concat([df_existing, pending_df], ignore_index=True)
        df_combined = clean_data(df_combined)
        
        # Save
        save_fn(df_combined, sheet)
        
        # Clear cache
        st.cache_data.clear()
        
        # Update state to COMPLETED
        ImportStateManager.set_state(
            ImportState.COMPLETED,
            f"✅ Successfully merged {len(pending_df)} rows!"
        )
        
        # Clear pending data
        ImportStateManager.clear_pending_data()
        
        # Bump data version for cache invalidation
        from data_manager import bump_data_version
        bump_data_version()
        
        return df_combined, True
        
    except Exception as e:
        ImportStateManager.set_state(
            ImportState.ERROR,
            f"Merge failed: {str(e)}"
        )
        return df_existing, False


# ============================================================
# 📤 Export Buttons (Unchanged)
# ============================================================
def export_buttons(df):
    """Provide buttons to export filtered or full dataset."""
    st.sidebar.markdown("---")
    st.sidebar.subheader("📤 Export Data")

    # --- CSV Export ---
    csv_data = df.to_csv(index=False).encode("utf-8")
    st.sidebar.download_button(
        label="💾 Download CSV",
        data=csv_data,
        file_name="expenses_export.csv",
        mime="text/csv",
    )

    # --- Excel Export ---
    try:
        output = BytesIO()
        df.to_excel(output, index=False, sheet_name="Expenses")
        st.sidebar.download_button(
            label="📘 Download Excel",
            data=output.getvalue(),
            file_name="expenses_export.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        st.sidebar.warning(f"Excel export unavailable: {e}")