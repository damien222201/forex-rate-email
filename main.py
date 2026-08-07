"""
Daily forex rate email.

Fetches current NGN value of 1 USD, 1 GBP, 1 EUR, and 1 CAD from the
free open.er-api.com endpoint, compares against yesterday's snapshot
(stored in last_rates.json in this repo), and emails a summary via
SMTP showing the ₦ difference and % change since yesterday.

Environment variables (set as GitHub Actions secrets):
    SMTP_HOST       e.g. smtp.gmail.com
    SMTP_PORT       e.g. 587
    SMTP_USER       the Gmail address sending the email
    SMTP_PASSWORD   a Gmail App Password (NOT your normal password)
    EMAIL_TO        address(es) to send the report to (comma-separated ok)
"""

import json
import os
import smtplib
import sys
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

CURRENCIES = {
    "USD": "US Dollar",
    "GBP": "British Pound",
    "EUR": "Euro",
    "CAD": "Canadian Dollar",
}

API_URL = "https://open.er-api.com/v6/latest/USD"
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "last_rates.json")


def fetch_rates() -> dict:
    """Fetch USD-based rates and derive NGN value of 1 unit of each tracked currency."""
    resp = requests.get(API_URL, timeout=15)
    resp.raise_for_status()
    payload = resp.json()

    if payload.get("result") != "success":
        raise RuntimeError(f"API did not return success: {payload}")

    rates = payload["rates"]
    ngn_per_usd = rates["NGN"]

    ngn_values = {}
    for code in CURRENCIES:
        if code == "USD":
            ngn_values["USD"] = ngn_per_usd
        else:
            # rates[code] = units of `code` per 1 USD
            # so 1 unit of `code` = ngn_per_usd / rates[code] naira
            ngn_values[code] = ngn_per_usd / rates[code]

    return ngn_values


def load_previous_rates() -> dict:
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_current_rates(data: dict) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def format_ngn(value: float) -> str:
    return f"₦{value:,.2f}"


def format_diff(value: float) -> str:
    sign = "+" if value >= 0 else "-"
    return f"{sign}₦{abs(value):,.2f}"


def build_email_body(current: dict, previous: dict) -> tuple[str, str]:
    today = datetime.now(timezone.utc).strftime("%A, %B %d, %Y")
    has_previous = bool(previous)

    text_lines = [f"Forex Rate Report — {today}\n"]
    if not has_previous:
        text_lines.append("(First run — no previous-day comparison yet.)\n")
    html_rows = []

    for code, name in CURRENCIES.items():
        current_ngn = current.get(code)
        if current_ngn is None:
            continue

        current_str = format_ngn(current_ngn)
        prev_ngn = previous.get(code)

        if prev_ngn:
            diff = current_ngn - prev_ngn
            pct_change = (diff / prev_ngn) * 100
            arrow = "▲" if diff >= 0 else "▼"
            color = "#1a9c4c" if diff >= 0 else "#d13c3c"
            diff_str = format_diff(diff)
            change_str = f"{arrow} {diff_str} ({abs(pct_change):.2f}%)"
        else:
            change_str = "N/A (no data from yesterday)"
            color = "#666666"

        text_lines.append(f"1 {code} ({name}) = {current_str}   Change: {change_str}")
        html_rows.append(
            f"<tr>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #eee;'>{code} — {name}</td>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #eee;text-align:right;'>{current_str}</td>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #eee;text-align:right;color:{color};font-weight:bold;font-size:13px;'>{change_str}</td>"
            f"</tr>"
        )

    text_body = "\n".join(text_lines)

    note = "" if has_previous else "<p style='color:#999;font-size:12px;'>First run — no previous-day comparison yet.</p>"

    html_body = f"""\
<html>
  <body style="font-family:Arial,sans-serif;background:#f7f7f7;padding:20px;">
    <div style="max-width:520px;margin:auto;background:#fff;border-radius:8px;padding:24px;">
      <h2 style="margin-top:0;">💱 Forex Rate Report</h2>
      <p style="color:#666;margin-top:-10px;">{today}</p>
      {note}
      <table style="width:100%;border-collapse:collapse;font-size:14px;">
        <thead>
          <tr style="background:#fafafa;">
            <th style="text-align:left;padding:8px 12px;">Currency</th>
            <th style="text-align:right;padding:8px 12px;">Rate (NGN)</th>
            <th style="text-align:right;padding:8px 12px;">Change vs Yesterday</th>
          </tr>
        </thead>
        <tbody>
          {''.join(html_rows)}
        </tbody>
      </table>
      <p style="color:#999;font-size:12px;margin-top:20px;">Data via open.er-api.com (ExchangeRate-API)</p>
    </div>
  </body>
</html>
"""
    return text_body, html_body


def send_email(text_body: str, html_body: str) -> None:
    smtp_host = os.environ["SMTP_HOST"]
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ["SMTP_USER"]
    smtp_password = os.environ["SMTP_PASSWORD"]
    email_to = os.environ["EMAIL_TO"]

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Forex Rate Report — {today}"
    msg["From"] = smtp_user
    msg["To"] = email_to

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, email_to.split(","), msg.as_string())


def main():
    try:
        current = fetch_rates()
    except (requests.RequestException, RuntimeError, KeyError) as e:
        print(f"Failed to fetch rates: {e}", file=sys.stderr)
        sys.exit(1)

    previous = load_previous_rates()
    text_body, html_body = build_email_body(current, previous)

    try:
        send_email(text_body, html_body)
    except Exception as e:
        print(f"Failed to send email: {e}", file=sys.stderr)
        sys.exit(1)

    save_current_rates(current)

    print("Email sent successfully.")
    print(text_body)


if __name__ == "__main__":
    main()
