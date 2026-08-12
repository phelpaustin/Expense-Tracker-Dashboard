# settings_page.py
"""
Settings page for alert preferences and email configuration.
Allows users to configure budget alert thresholds, email notifications, and daily summaries.
"""
import streamlit as st
from datetime import time
import json
from pathlib import Path
import os
from dotenv import load_dotenv

# Persistence now lives in settings_manager (single source of truth).
# Re-exported here so existing imports like
# ``from settings_page import load_alert_settings`` keep working.
from settings_manager import (
    ALERT_SETTINGS_FILE as SETTINGS_FILE,
    load_alert_settings,
    save_alert_settings,
    get_default_alert_settings as get_default_settings,
)

load_dotenv()


def render_settings_page(df=None):
    """Render the settings page with alert preferences."""
    st.title("⚙️ Settings & Preferences")
    
    # Load current settings
    settings = load_alert_settings()
    
    # Create tabs
    tab1, tab2, tab3 = st.tabs(["🔔 Alerts", "📧 Email", "📖 Help"])
    
    # ═══════════════════════════════════════════════════════════
    # TAB 1: ALERT PREFERENCES
    # ═══════════════════════════════════════════════════════════
    with tab1:
        st.markdown("### 🔔 Budget Alert Preferences")
        st.caption("Control when and how you receive budget alerts")
        
        alerts_enabled = st.checkbox(
            "Enable budget alerts",
            value=settings.get("alerts_enabled", True),
            help="Master switch for all alert types"
        )
        
        if alerts_enabled:
            st.markdown("---")
            st.markdown("#### 📊 Threshold Alerts")
            st.caption("Get notified when you reach certain % of your budget")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                alert_80 = st.checkbox(
                    "🟡 Alert at 80%",
                    value=settings.get("threshold_80", True),
                    help="Caution: approaching budget limit"
                )
            
            with col2:
                alert_90 = st.checkbox(
                    "🟠 Alert at 90%",
                    value=settings.get("threshold_90", True),
                    help="Warning: very close to limit"
                )
            
            with col3:
                alert_100 = st.checkbox(
                    "🔴 Alert when exceeded",
                    value=settings.get("threshold_100", True),
                    help="Critical: budget exceeded"
                )
            
            st.markdown("---")
            st.markdown("#### 🔮 Predictive Alerts")
            st.caption("Get warned before you exceed budget based on spending trends")
            
            predictive_alerts = st.checkbox(
                "Enable predictive alerts",
                value=settings.get("predictive_alerts", True),
                help="'At current rate, you'll exceed budget in X days'"
            )
            
            if predictive_alerts:
                st.info("💡 Example: *At current rate, you'll exceed Groceries budget in 5 days*")
            
            st.markdown("---")
            st.markdown("#### ⚡ Velocity Alerts")
            st.caption("Get notified when spending unusually fast compared to your average")
            
            velocity_alerts = st.checkbox(
                "Enable velocity alerts",
                value=settings.get("velocity_alerts", True),
                help="'Your spending is 2x faster than usual'"
            )
            
            if velocity_alerts:
                st.info("💡 Example: *Your Dining spending is 2.5x your usual rate*")
            
            # Save button for alerts tab
            st.markdown("---")
            if st.button("💾 Save Alert Preferences", key="save_alerts", type="primary", width="stretch"):
                settings["alerts_enabled"] = alerts_enabled
                settings["threshold_80"] = alert_80
                settings["threshold_90"] = alert_90
                settings["threshold_100"] = alert_100
                settings["predictive_alerts"] = predictive_alerts
                settings["velocity_alerts"] = velocity_alerts
                save_alert_settings(settings)
                st.success("✅ Alert preferences saved!")
                st.balloons()
                st.rerun()
        
        else:
            st.info("💡 Enable alerts above to configure preferences")
    
    # ═══════════════════════════════════════════════════════════
    # TAB 2: EMAIL CONFIGURATION
    # ═══════════════════════════════════════════════════════════
    with tab2:
        st.markdown("### 📧 Email Notifications")
        
        # Check if email is configured
        sender_email = os.getenv("SENDER_EMAIL")
        sender_password = os.getenv("SENDER_PASSWORD")
        receiver_email = os.getenv("RECEIVER_EMAIL")
        
        email_configured = all([sender_email, sender_password, receiver_email])
        
        if email_configured:
            st.success(f"✅ Email configured: {sender_email}")
        else:
            st.warning("⚠️ Email not configured. See setup instructions in Help tab.")
        
        st.markdown("---")
        
        # Test email button
        if email_configured:
            col_test1, col_test2, col_test3 = st.columns([1, 1, 1])
            
            with col_test1:
                if st.button("🧪 Send Test Email", type="primary", width="stretch"):
                    try:
                        from notification_manager import test_email_configuration
                        with st.spinner("Sending test email..."):
                            success, error = test_email_configuration()
                        if success:
                            st.success("✅ Test email sent! Check your inbox.")
                        else:
                            st.error(f"❌ Failed {error}. Check your .env file.")
                    except ImportError:
                        st.error("❌ notification_manager.py not found")
            
            with col_test2:
                if st.button("🔴 Test Budget Alert", width="stretch"):
                    try:
                        from notification_manager import send_budget_alert_email
                        with st.spinner("Sending test alert..."):
                            success, error = send_budget_alert_email(
                                df,
                                alert_title="Test Budget Alert",
                                alert_message="This is a test budget alert from your Expense Tracker.",
                                severity="warning"
                            )
                        if success:
                            st.success("✅ Alert email sent!")
                        else:
                            st.error(f"❌ Failed: {error}")
                    except ImportError:
                        st.error("❌ notification_manager.py not found")
            
            with col_test3:
                if st.button("📊 Test Daily Summary", width="stretch"):
                    try:
                        from notification_manager import send_daily_summary_email
                        with st.spinner("Sending daily summary..."):
                            success, error = send_daily_summary_email(df)
                        if success:
                            st.success("✅ Daily summary sent!")
                        else:
                            st.error(f"❌ Failed: {error}")
                    except ImportError:
                        st.error("❌ notification_manager.py not found")
        
        st.markdown("---")
        st.markdown("#### 📅 Daily Summary")
        st.caption("Receive a daily email with spending summary and alerts")
        
        daily_summary_enabled = st.checkbox(
            "Send daily summary email",
            value=settings.get("daily_summary_enabled", False),
            help="Receive spending summary every day",
            disabled=not email_configured
        )
        
        if daily_summary_enabled:
            summary_time_str = settings.get("daily_summary_time", "18:00")
            hour, minute = map(int, summary_time_str.split(":"))
            summary_time = st.time_input(
                "Delivery time",
                value=time(hour, minute),
                help="What time should we send the summary?"
            )
            settings["daily_summary_time"] = summary_time.strftime("%H:%M")
            
            st.info(f"📬 You'll receive daily summaries at {summary_time.strftime('%I:%M %p')}")
        
        st.markdown("---")
        st.markdown("#### 📊 Weekly Summary")
        st.caption("Receive a weekly recap every Monday")
        
        weekly_summary_enabled = st.checkbox(
            "Send weekly summary email",
            value=settings.get("weekly_summary_enabled", False),
            help="Receive spending summary every Monday",
            disabled=not email_configured
        )
        
        if weekly_summary_enabled:
            st.info("📬 You'll receive weekly summaries every Monday at 9:00 AM")
        
        # Save button for email tab
        st.markdown("---")
        if st.button("💾 Save Email Preferences", key="save_email", type="primary", width="stretch"):
            settings["daily_summary_enabled"] = daily_summary_enabled
            settings["weekly_summary_enabled"] = weekly_summary_enabled
            save_alert_settings(settings)
            st.success("✅ Email preferences saved!")
            st.rerun()
        
        # Current settings summary
        if email_configured:
            st.markdown("---")
            st.markdown("#### 📋 Current Settings")
            st.info(f"""
**Email**: {sender_email}  
**Daily Summary**: {'✅ Enabled' if settings.get('daily_summary_enabled') else '❌ Disabled'}  
**Weekly Summary**: {'✅ Enabled' if settings.get('weekly_summary_enabled') else '❌ Disabled'}
            """)
    
    # ═══════════════════════════════════════════════════════════
    # TAB 3: HELP & SETUP INSTRUCTIONS
    # ═══════════════════════════════════════════════════════════
    with tab3:
        st.markdown("### 📖 Gmail Setup Instructions")
        
        # Check current status
        sender_email = os.getenv("SENDER_EMAIL")
        sender_password = os.getenv("SENDER_PASSWORD")
        receiver_email = os.getenv("RECEIVER_EMAIL")
        
        st.markdown("#### ✅ Configuration Checklist")
        
        col_status1, col_status2 = st.columns([3, 1])
        with col_status1:
            st.write("SMTP Server configured")
        with col_status2:
            st.write("✅" if os.getenv("SMTP_SERVER") else "❌")
        
        col_status3, col_status4 = st.columns([3, 1])
        with col_status3:
            st.write("Sender email configured")
        with col_status4:
            st.write("✅" if sender_email else "❌")
        
        col_status5, col_status6 = st.columns([3, 1])
        with col_status5:
            st.write("Sender password configured")
        with col_status6:
            st.write("✅" if sender_password else "❌")
        
        col_status7, col_status8 = st.columns([3, 1])
        with col_status7:
            st.write("Receiver email configured")
        with col_status8:
            st.write("✅" if receiver_email else "❌")
        
        st.markdown("---")
        
        with st.expander("📝 Step-by-Step Setup Guide", expanded=not all([sender_email, sender_password, receiver_email])):
            st.markdown("""
### 🎯 Complete Setup in 5 Minutes

#### Step 1: Get Gmail App Password (2 minutes)
1. Go to: https://myaccount.google.com/security
2. Click "2-Step Verification" (enable if not already)
3. Search for "App passwords"
4. Click "App passwords"
5. Select "Mail" and "Other (Custom name)"
6. Name it: "Expense Tracker"
7. Click "Generate"
8. **COPY the 16-character password** (e.g., `abcd efgh ijkl mnop`)

#### Step 2: Create .env File (2 minutes)
1. Open your Expense-Tracker-Dashboard folder
2. Create a new file named `.env` (yes, starts with a dot!)
3. Copy-paste this template:

```env
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your.email@gmail.com
SENDER_PASSWORD=abcd efgh ijkl mnop
RECEIVER_EMAIL=your.email@gmail.com
```

4. Replace `your.email@gmail.com` with YOUR Gmail address
5. Replace `abcd efgh ijkl mnop` with the password from Step 1
6. Save the file

#### Step 3: Install Package (1 minute)
Open terminal and run:
```bash
pip install python-dotenv
```

#### Step 4: Test Configuration
1. Restart this app
2. Come back to Settings → Email tab
3. Click "🧪 Send Test Email"
4. Check your Gmail inbox!

---

### 🆘 Troubleshooting

**Problem**: Authentication failed  
**Solution**: Make sure you're using the App Password (16 chars), not your regular Gmail password

**Problem**: Can't find .env file  
**Solution**: Enable "Show hidden files" in File Explorer (Windows) or use `ls -la` in terminal

**Problem**: Module 'dotenv' not found  
**Solution**: Run `pip install python-dotenv`

**Problem**: Test email not arriving  
**Solution**: Check Spam folder, wait 1 minute, verify .env file location

---

### 📧 Example .env File

```env
# Email Configuration for Gmail
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=myexpensetracker@gmail.com
SENDER_PASSWORD=wxyz abcd efgh ijkl
RECEIVER_EMAIL=myexpensetracker@gmail.com
```

⚠️ **Important**: Never commit .env file to git! Add it to .gitignore
            """)
        
        with st.expander("💡 Tips & Best Practices"):
            st.markdown("""
### 💡 Tips for Best Results

1. **Use a dedicated Gmail account** for your expense tracker
   - Don't use your primary personal/work email
   - Create a free Gmail just for this purpose

2. **Keep your App Password secure**
   - Store it only in .env file
   - Never share it or commit to git
   - Can revoke and regenerate anytime

3. **Test regularly**
   - Send test emails monthly to ensure it still works
   - Gmail App Passwords sometimes expire if unused

4. **Organize your inbox**
   - Create Gmail filter for expense tracker emails
   - Auto-label them for easy access
   - Star important alert emails

5. **Daily summary timing**
   - Set for evening (6-8 PM) to review before bed
   - Or morning (8-9 AM) to plan the day
   - Choose time when you'll actually read it

6. **Alert fatigue prevention**
   - Don't enable ALL alerts at once
   - Start with just 90% and 100% thresholds
   - Add predictive alerts after you're comfortable
            """)
        
        with st.expander("🔐 Security & Privacy"):
            st.markdown("""
### 🔐 Security Information

**Is this secure?**  
✅ Yes, when done correctly:
- App Passwords are single-purpose and revocable
- .env file is local-only (not uploaded anywhere)
- SMTP connection uses TLS encryption
- Only you have access to your data

**What if someone gets my App Password?**  
- They can only send emails from that account
- They cannot access your Gmail inbox
- You can revoke it instantly at myaccount.google.com/security
- Generate a new one in seconds

**Where is my data stored?**  
- .env file: Local on your computer only
- Email credentials: Never uploaded to cloud
- Expense data: Stays in your local data folder
- No external services access your financial data

**Best practices:**
1. Use a dedicated Gmail account (not your main one)
2. Never commit .env to git (add to .gitignore)
3. Revoke App Password if you stop using the app
4. Keep your computer secure with password/encryption
            """)


# For testing settings page standalone
if __name__ == "__main__":
    render_settings_page(df=None)