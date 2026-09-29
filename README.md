# Telegram Commission Report Bot

A zero-cost Telegram bot for a real use case: a mobile-money agent shares
their Telegram-verified phone number, the bot matches it to their **Master**
number in an agent directory, and instantly replies with their full
commission report — pulled live from your Google Sheet — laid out exactly
like your existing Excel template.

## How it works

```
Agent taps "Share my phone number" in Telegram
        ↓
Telegram sends the number tied to their OWN account (can't be spoofed)
        ↓
Bot looks up that phone in the "agents" cache (from Fcc_Data)  ->  Master
        ↓
Bot looks up that Master in the "commission" cache (from Fcc_Commission)
        ↓
Bot replies with the full 39-field report, formatted like your template
```

## The one security rule this was built around

**Verification only works through Telegram's native "Share Contact" button —
there is no way to type a phone number instead.** Two checks enforce this:

1. The button (`request_contact`) can only ever hand Telegram the number
   registered to the account currently pressing it — Telegram doesn't allow
   it to send an arbitrary number.
2. The bot additionally checks `contact.user_id == the sender's own Telegram
   ID`. This blocks the one edge case Telegram itself doesn't prevent:
   someone attaching a contact card from their address book instead of using
   the button. If the two IDs don't match, the bot refuses and shows nothing.

Anyone who types a number instead of using the button gets told to use the
button — nothing is ever looked up from typed text.

## Data source

Two tabs, kept in **one Google Sheet** for simplicity (recommended — see
setup below):

| Tab | Same shape as | Required columns |
|---|---|---|
| Agents directory | `Fcc_Data.xlsx` | `Master`, `Name`, `Phone num` (`اسم الوكالة` optional) |
| Commission table | `Fcc_Commission_New.xlsx` → **Sheet1** (the flat table, not the single-record template tab) | `Master` + whatever report columns you track |

Verified against your actual uploaded files: 103 agents, 494 commission
rows, 0 skipped, 0 duplicate phone numbers, every agent's Master present in
the commission table.

The bot never re-reads these on every message — a background sync every
`SYNC_INTERVAL_MINUTES` (default 15) refreshes a local SQLite cache, and an
admin can force it instantly with `/sync`. See the original architecture
notes below for why.

## Report formatting

The reply matches your Excel template field-for-field, in the same order:
Master, Gov, Area, Rep, SV, MGR, Category, Target 293, 293 MTD ... down to
Tiers (see `app/services/report_formatting.py` for the exact list). Number
formatting rules, matched to your template:

- Text fields (Master, Gov, Area, Rep, SV, MGR, Category, Tiers) — shown as-is
- `%` and `%2` — shown as a rounded whole-number percentage (0.11 → `11%`)
- Every other field — comma-separated, rounded to the nearest whole number,
  and shown as `-` when the value is exactly 0 (matching your template's
  blank/zero cells)

If your commission sheet's columns ever change name or order, only
`FIELD_ORDER` in `report_formatting.py` needs updating — the sync and lookup
logic don't hard-code column names beyond `Master`.

## 1. Google API setup

1. https://console.cloud.google.com/ → new project → enable **Google Sheets
   API** and **Google Drive API** (both free).
2. Credentials → Create Credentials → Service account → create a key (JSON) →
   save it as `credentials/service-account.json` in this project
   (already git-ignored, never commit it).
3. Create one Google Sheet with two tabs, named to match
   `GOOGLE_SHEET_AGENTS_WORKSHEET` and `GOOGLE_SHEET_COMMISSION_WORKSHEET`
   in your `.env` (defaults: `Fcc_Data` and `Fcc_Commission`). Paste in the
   contents of your two Excel files — for the commission tab, use the flat
   "Sheet1" table, not the single-record template tab.
4. Share the Sheet with your service account's email (shown in its JSON key)
   as **Viewer**.
5. Copy the Sheet ID from its URL into `GOOGLE_SHEET_ID`.

## 2. Telegram bot setup

1. @BotFather → `/newbot` → copy the token into `TELEGRAM_BOT_TOKEN`.
2. @userinfobot → copy your numeric ID into `ADMIN_TELEGRAM_IDS`.

## 3. Local setup

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# fill in .env
python main.py
```

`RUN_MODE=polling` (default) needs no public URL — message your bot `/start`.

## 4. Running tests

```bash
pip install pytest
pytest
```

Covers: phone normalization, phone → agent → commission-report lookup using
your real Master 1153420 record, duplicate-phone handling, and the report
formatting rules (percent rounding, comma formatting, zero → `-`) verified
against the exact numbers from your screenshot.

## 5. Deploying to Render (free)

Same as any Python web service: New → Web Service → connect your repo,
build command `pip install -r requirements.txt`, start command
`python main.py`, set every `.env` variable plus `RUN_MODE=webhook` and
`WEBHOOK_BASE_URL=https://<your-service>.onrender.com`. Free tier sleeps
after 15 minutes idle (30–50s wake delay on the next message) — see the
cost breakdown in the project's original design notes if you want the
full free-vs-paid comparison.

## 6. Admin commands

Restricted to `ADMIN_TELEGRAM_IDS`:

- `/sync` — refresh agents + commission data from Google now
- `/stats` — counts + last sync time
- `/find <query>` — search by Master, agent name, agency, or phone
- `/duplicates` — list any phone numbers shared by more than one agent
- `/adminhelp` — list these commands

## 7. Troubleshooting

| Symptom | Likely cause |
|---|---|
| "الرقم ده مش مسجل عندنا كوكيل" for a number you know is in the sheet | Run `/sync` — cache may be stale, or the number's format doesn't normalize to `+20...` |
| "الرقم ده مش رقمك المسجل على تليجرام" | Expected — the agent tried a typed number or someone else's contact card; ask them to use the share-contact button with their own account |
| "تم التحقق... لكن لسه مفيش تقرير كوميشن متاح" | The agent's Master exists in the agents tab but not (yet) in the commission tab — check the sheet, then `/sync` |
| `/sync` reports skipped rows | Logs name the exact row/column — one bad row never blocks the rest |
| Google API errors during sync | Confirm the Sheet is shared with the service account's email, both APIs are enabled, and both tab names match your `.env` |
