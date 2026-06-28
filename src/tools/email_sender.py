"""
Email Sender

Formats a list of paper recommendations as an HTML email and sends it
via Gmail SMTP using credentials from config.py.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

import config


def _build_html(papers: list[dict]) -> str:
    date_str = datetime.now().strftime("%B %d, %Y")
    rows = ""
    for p in papers:
        confidence_pct = int(p.get("confidence", 0) * 100)
        rows += f"""
        <tr>
          <td style="padding:12px 0; border-bottom:1px solid #eee;">
            <a href="{p.get('arxiv_url', '#')}" style="font-size:16px;font-weight:bold;color:#1a73e8;text-decoration:none;">
              {p.get('title', 'Untitled')}
            </a><br>
            <span style="color:#555;font-size:13px;">{p.get('why_relevant', '')}</span><br>
            <span style="color:#888;font-size:12px;">Relevance: {confidence_pct}%</span>
          </td>
        </tr>"""

    return f"""
    <html><body style="font-family:Arial,sans-serif;max-width:640px;margin:auto;color:#333;">
      <h2 style="color:#1a73e8;">Weaver — Paper Recommendations</h2>
      <p style="color:#666;">{date_str}</p>
      <table width="100%" cellpadding="0" cellspacing="0">
        {rows}
      </table>
      <p style="margin-top:24px;color:#aaa;font-size:11px;">
        Sent by Weaver · your personal research knowledge graph
      </p>
    </body></html>
    """


def send_recommendations(papers: list[dict], to_address: str | None = None) -> dict:
    """
    Send a list of paper recommendations as an HTML email.

    Args:
        papers:     List of recommendation dicts (title, arxiv_url, why_relevant, confidence).
        to_address: Override recipient; defaults to config.EMAIL_TO.

    Returns:
        {"success": bool, "message": str}
    """
    if not papers:
        return {"success": False, "message": "No papers to send."}

    recipient = to_address or config.EMAIL_TO
    subject   = f"Weaver: {len(papers)} new paper recommendation{'s' if len(papers) != 1 else ''}"
    html_body = _build_html(papers)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = config.EMAIL_ADDRESS
    msg["To"]      = recipient
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(config.EMAIL_ADDRESS, config.EMAIL_PASSWORD)
            server.sendmail(config.EMAIL_ADDRESS, recipient, msg.as_string())
        return {"success": True, "message": f"Email sent to {recipient}"}
    except smtplib.SMTPAuthenticationError:
        return {"success": False, "message": "SMTP authentication failed — check EMAIL_ADDRESS and EMAIL_PASSWORD in .env"}
    except Exception as e:
        return {"success": False, "message": f"Email error: {e}"}
