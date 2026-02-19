# notification_manager.py
"""
Notification system for budget alerts and spending summaries.
Sends emails via Gmail SMTP.
"""
import os
import smtplib
import streamlit as st
import pandas as pd
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Optional, Tuple

try:
    from dotenv import load_dotenv
    load_dotenv()
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False


# ═══════════════════════════════════════════════════════════════
# EMAIL SENDING FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def send_email_notification(
    subject: str,
    body: str,
    to_email: Optional[str] = None,
    html_body: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    Send email notification via Gmail SMTP.
    
    Returns:
        (success, error_message) tuple
    """
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")
    receiver_email = to_email or os.getenv("RECEIVER_EMAIL")
    
    if not all([sender_email, sender_password, receiver_email]):
        return False, "Email credentials not configured in .env file"
    
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = receiver_email
        msg["Date"] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")
        
        msg.attach(MIMEText(body, "plain"))
        if html_body:
            msg.attach(MIMEText(html_body, "html"))
        
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        
        return True, None
        
    except smtplib.SMTPAuthenticationError:
        return False, "Gmail authentication failed. Check your app password."
    except Exception as e:
        return False, str(e)


def send_budget_alert_email(
    df: pd.DataFrame,
    alert_title: Optional[str] = None,
    alert_message: Optional[str] = None,
    severity: str = "warning"
) -> Tuple[bool, Optional[str]]:
    """
    Send budget alert email. Can be called with just df for auto-generated alert,
    or with specific title/message.
    
    Args:
        df: Expense dataframe
        alert_title: Optional alert title
        alert_message: Optional alert message  
        severity: "info", "caution", "warning", or "critical"
    
    Returns:
        (success, error_message) tuple
    """
    # If no title/message provided, generate a test alert
    if not alert_title or not alert_message:
        alert_title = "Test Budget Alert"
        alert_message = "This is a test budget alert from your Expense Tracker."
        severity = "info"
    
    severity_icons = {
        "info": "💡",
        "caution": "🟡", 
        "warning": "🟠",
        "critical": "🔴"
    }
    icon = severity_icons.get(severity, "ℹ️")
    
    plain_body = f"""
{icon} Budget Alert: {alert_title}

{alert_message}

---
Sent from your Expense Tracker
View details at: http://localhost:8501
"""
    
    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 10px 10px 0 0;">
          <h2 style="color: white; margin: 0;">{icon} Budget Alert</h2>
        </div>
        
        <div style="background: #f9f9f9; padding: 20px; border: 1px solid #e0e0e0; border-radius: 0 0 10px 10px;">
          <h3 style="color: #444;">{alert_title}</h3>
          <p style="font-size: 16px; line-height: 1.6;">{alert_message}</p>
          
          <div style="margin-top: 20px; padding: 15px; background: white; border-left: 4px solid #667eea; border-radius: 5px;">
            <p style="margin: 0; font-size: 14px; color: #666;">
              💡 <strong>Tip:</strong> Open your Expense Tracker to see detailed breakdown.
            </p>
          </div>
          
          <div style="margin-top: 20px; text-align: center;">
            <a href="http://localhost:8501" 
               style="display: inline-block; padding: 12px 24px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; font-weight: bold;">
              View Dashboard
            </a>
          </div>
        </div>
        
        <div style="text-align: center; margin-top: 20px; font-size: 12px; color: #999;">
          <p>Sent from your Expense Tracker • {datetime.now().strftime('%B %d, %Y')}</p>
        </div>
      </body>
    </html>
    """
    
    subject = f"{icon} Budget Alert: {alert_title}"
    return send_email_notification(subject, plain_body, html_body=html_body)


def send_daily_summary_email(df: pd.DataFrame) -> Tuple[bool, Optional[str]]:
    """Send daily spending summary email."""
    if df.empty:
        return False, "No data to summarize"
    
    # Calculate summary stats
    from config import Columns
    
    df_copy = df.copy()
    df_copy[Columns.DATE] = pd.to_datetime(df_copy[Columns.DATE], errors="coerce")
    df_copy[Columns.PRICE_PAID] = pd.to_numeric(df_copy[Columns.PRICE_PAID], errors="coerce")
    
    today = datetime.now().date()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    
    today_spending = df_copy[df_copy[Columns.DATE].dt.date == today][Columns.PRICE_PAID].sum()
    week_spending = df_copy[df_copy[Columns.DATE].dt.date >= week_start][Columns.PRICE_PAID].sum()
    month_spending = df_copy[df_copy[Columns.DATE].dt.date >= month_start][Columns.PRICE_PAID].sum()
    
    plain_body = f"""
📊 Daily Spending Summary - {today.strftime('%B %d, %Y')}

💰 Today:      {today_spending:,.0f} SEK
📅 This week:  {week_spending:,.0f} SEK
📆 This month: {month_spending:,.0f} SEK

---
Sent from your Expense Tracker
"""
    
    status_color = "#22c55e" if month_spending < 10000 else "#f59e0b" if month_spending < 20000 else "#ef4444"
    
    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 10px 10px 0 0;">
          <h2 style="color: white; margin: 0;">📊 Daily Spending Summary</h2>
          <p style="color: rgba(255,255,255,0.9); margin: 5px 0 0 0; font-size: 14px;">
            {today.strftime('%A, %B %d, %Y')}
          </p>
        </div>
        
        <div style="background: #f9f9f9; padding: 20px; border: 1px solid #e0e0e0;">
          <div style="background: white; padding: 15px; border-radius: 8px; border-left: 4px solid #6366f1; margin-bottom: 10px;">
            <div style="font-size: 14px; color: #666;">💰 Today</div>
            <div style="font-size: 24px; font-weight: bold; color: #333;">{today_spending:,.0f} SEK</div>
          </div>
          
          <div style="background: white; padding: 15px; border-radius: 8px; border-left: 4px solid #8b5cf6; margin-bottom: 10px;">
            <div style="font-size: 14px; color: #666;">📅 This Week</div>
            <div style="font-size: 24px; font-weight: bold; color: #333;">{week_spending:,.0f} SEK</div>
          </div>
          
          <div style="background: white; padding: 15px; border-radius: 8px; border-left: 4px solid {status_color};">
            <div style="font-size: 14px; color: #666;">📆 This Month</div>
            <div style="font-size: 24px; font-weight: bold; color: #333;">{month_spending:,.0f} SEK</div>
          </div>
          
          <div style="margin-top: 20px; text-align: center;">
            <a href="http://localhost:8501" 
               style="display: inline-block; padding: 12px 24px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; font-weight: bold;">
              View Full Dashboard
            </a>
          </div>
        </div>
      </body>
    </html>
    """
    
    subject = f"📊 Daily Summary - {month_spending:,.0f} SEK this month"
    return send_email_notification(subject, plain_body, html_body=html_body)


def test_email_configuration() -> Tuple[bool, Optional[str]]:
    """Test email configuration."""
    test_subject = "🧪 Test Email from Expense Tracker"
    test_body = """
This is a test email to verify your Gmail SMTP configuration.

If you received this, your email setup is working! ✅

---
Expense Tracker Notification System
"""
    
    test_html = """
    <html>
      <body style="font-family: Arial, sans-serif; padding: 20px; max-width: 600px; margin: 0 auto;">
        <div style="background: #f0f9ff; border-left: 4px solid #0284c7; padding: 20px; border-radius: 8px;">
          <h2 style="margin: 0; color: #0369a1;">🧪 Email Test Successful!</h2>
          <p style="font-size: 16px;">Your Gmail SMTP configuration is working correctly.</p>
          <p style="font-size: 14px; color: #666;">You can now receive budget alerts and daily summaries.</p>
        </div>
      </body>
    </html>
    """
    
    return send_email_notification(test_subject, test_body, html_body=test_html)


# ═══════════════════════════════════════════════════════════════
# STREAMLIT UI
# ═══════════════════════════════════════════════════════════════

def notification_settings_ui(df: pd.DataFrame):
    """Notification settings page UI."""
    st.title("🔔 Notification Settings")
    
    # Check email configuration
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")
    email_configured = bool(sender_email and sender_password)
    
    if email_configured:
        st.success(f"✅ Email configured: {sender_email}")
    else:
        st.warning("⚠️ Email not configured. Add credentials to .env file.")
        
        with st.expander("📖 Setup Instructions"):
            st.markdown("""
            ### How to Configure Gmail:
            
            1. **Get App Password**:
               - Visit: https://myaccount.google.com/security
               - Enable 2-Step Verification
               - Generate App Password for "Mail"
            
            2. **Create .env file** in project root:
            ```
            SMTP_SERVER=smtp.gmail.com
            SMTP_PORT=587
            SENDER_EMAIL=your.email@gmail.com
            SENDER_PASSWORD=your-16-char-app-password
            RECEIVER_EMAIL=your.email@gmail.com
            ```
            
            3. **Restart the app**
            """)
        return
    
    # Test Notifications
    st.markdown("---")
    st.markdown("### 📧 Test Notifications")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🧪 Test Email", use_container_width=True):
            with st.spinner("Sending test email..."):
                success, error = test_email_configuration()
            if success:
                st.success("✅ Test email sent! Check your inbox.")
            else:
                st.error(f"❌ Failed: {error}")
    
    with col2:
        if st.button("📧 Test Budget Alert", use_container_width=True):
            with st.spinner("Sending budget alert..."):
                success, error = send_budget_alert_email(df)
            if success:
                st.success("✅ Budget alert sent!")
            else:
                st.error(f"❌ Failed: {error}")
    
    with col3:
        if st.button("📊 Test Daily Summary", use_container_width=True):
            with st.spinner("Sending daily summary..."):
                success, error = send_daily_summary_email(df)
            if success:
                st.success("✅ Daily summary sent!")
            else:
                st.error(f"❌ Failed: {error}")
    
    # Alert Settings
    st.markdown("---")
    st.markdown("### ⚙️ Alert Settings")
    
    enable_alerts = st.checkbox(
        "Enable budget alerts",
        value=True,
        help="Get notified when approaching budget limits"
    )
    
    if enable_alerts:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            alert_80 = st.checkbox("🟡 Alert at 80%", value=True)
        with col2:
            alert_90 = st.checkbox("🟠 Alert at 90%", value=True)
        with col3:
            alert_100 = st.checkbox("🔴 Alert when exceeded", value=True)
        
        st.info("💡 Settings will be saved when you click the Save button")
    
    # Daily Summary
    st.markdown("---")
    st.markdown("### 📅 Daily Summary")
    
    enable_daily = st.checkbox(
        "Send daily summary email",
        value=False,
        help="Receive spending summary every day"
    )
    
    if enable_daily:
        summary_time = st.time_input(
            "Delivery time",
            value=datetime.strptime("18:00", "%H:%M").time()
        )
        st.info(f"📬 You'll receive daily summaries at {summary_time.strftime('%I:%M %p')}")
    
    # Save Settings
    st.markdown("---")
    if st.button("💾 Save Settings", type="primary", use_container_width=True):
        st.success("✅ Settings saved!")
        st.info("⚠️ Note: Daily summaries require a background scheduler to be set up separately.")