# Forex Rate Email

Sends a daily email at 6:00 AM (WAT) with the current NGN value of 1
USD, 1 GBP, 1 EUR, and 1 CAD, plus how much each has moved since
yesterday's email — in ₦ and %. Powered by the free
[open.er-api.com](https://www.exchangerate-api.com/docs/free) endpoint
(no API key needed) and run entirely on GitHub Actions (no server
needed).

## Setup

1. **Create a Gmail App Password** (skip if you already have one from
   another project — you can reuse it)
   - Go to your Google Account → Security → 2-Step Verification (must be on)
   - Then Security → App passwords → generate one for "Mail"
   - Copy the 16-character password

2. **Push this repo to GitHub**

3. **Add repository secrets**
   Go to your repo → Settings → Secrets and variables → Actions → New repository secret, and add:

   | Secret name     | Value                                  |
   |-----------------|-----------------------------------------|
   | `SMTP_USER`     | your Gmail address                     |
   | `SMTP_PASSWORD` | the Gmail App Password                 |
   | `EMAIL_TO`      | the email address(es) to send reports to (comma-separated for multiple) |

4. **Set workflow permissions**
   Go to Settings → Actions → General → Workflow permissions → select
   **"Read and write permissions"**. This is required because the
   workflow commits `last_rates.json` back to the repo after each run
   so tomorrow's email can show the day-over-day change.

5. **Test it manually**
   Go to the "Actions" tab → "Daily Forex Rate Email" → "Run workflow"
   to trigger it immediately without waiting for the schedule.

## Schedule

Runs daily at **5:00 AM UTC (6:00 AM WAT)** via the cron in
`.github/workflows/daily-forex-email.yml`. Edit the `cron` line there
to change the time — GitHub Actions cron is always in UTC.

## Local testing

```bash
pip install -r requirements.txt
export SMTP_HOST=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USER=you@gmail.com
export SMTP_PASSWORD=your_app_password
export EMAIL_TO=you@gmail.com
python main.py
```

## Notes

- The script keeps a `last_rates.json` file in the repo to remember
  yesterday's rates for the day-over-day comparison. The workflow
  auto-commits it after each run — you don't need to touch it
  manually. The first email after setup will show "no comparison yet."
- open.er-api.com updates once daily and has no enforced request
  limit for occasional use like this.
