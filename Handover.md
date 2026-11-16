# Laxmi Daak - Handover Guide

Everything a new owner, developer or AI assistant needs to run, change and keep this project healthy.
Read this file first, then [RELEASE.md](RELEASE.md) (how to ship a change) and [README.md](README.md).

> **Keep secrets out of GitHub.** This repository is made public for short periods (free CI minutes).
> Never write passwords, the server IP, the SSH key name or `.env` values in this file, in code, or in
> commit messages. Keep those in a private note (password manager) that is not in the repository.

---

## 1. What the system is

Laxmi Daak is the internal courier / parcel tracking web app of Laxmi India Finance Ltd.
Branches, departments and the head office dispatch parcels, scan them as they move, and get e-mail alerts.

| Item | Value |
|---|---|
| Stack | Python 3, Flask 3, SQLAlchemy (SQLite), Flask-Login, Flask-WTF (CSRF), Flask-SocketIO |
| Front end | Jinja templates, plain CSS / JS (no build step) |
| Production | AWS EC2 (Ubuntu), nginx -> app on port 5000, `courier.service` (systemd) |
| Live URL | https://laxmidaak.lifc.in |
| Code | GitHub repo `dsnai11/Laxmi-Daak`, branch `main` = production |
| E-mail | SMTP (see `.env.example`), sent from background threads |
| Courier API | Pushpak Courier (booking, pickup, tracking) |

### Who uses it (roles)

| Screen name | Database role | What they do |
|---|---|---|
| **Admin** | `superadmin` | Sees everything, manages accounts, branches, departments, billing, security logs |
| **DO** | `manager` | A branch login (one per branch, plus a few at Jaipur HO). Dispatches, scans, receives |
| **Department** | `employee` | A person in a department. Raises queries, sees only their own parcels |

"Branch Manager" was renamed **DO** everywhere on screen. The database value is still `manager`.

### Parcel lifecycle (status values)

`pending` -> `in_transit` -> `delivered` (auto-archived) ; side paths: `failed`, `returned`.
Department query flow: `query_raised` -> `picked_up` -> `delivered_pending` -> `closed`.

---

## 2. Repository map

```
app/
  __init__.py        app factory, startup repairs, /healthz, 403 page, Socket.IO rooms
  config.py          settings read from .env
  models/            user.py, parcel.py (visibility rules live here), scan_log.py, branch.py ...
  routes/            auth, dashboard, dispatch (lists, new, edit), scan, admin, reports, api, tracking
  services/          email_service, import_service (Excel), qr_service, pushpak_service
  templates/         Jinja pages (base.html = layout + sidebar)
  utils.py           ist_today_start() (India "today")
deploy/              auto_update.sh + systemd timer (server pulls main every 5 min)
tests/               pytest suite (runs on an in-memory database)
.github/workflows/   ci.yml (tests), verify-deploy.yml (checks the live commit), deploy.yml (manual)
RELEASE.md           the release procedure
```

---

## 3. Run it on your own computer

```bash
git clone https://github.com/dsnai11/Laxmi-Daak.git
cd Laxmi-Daak
python -m venv venv
venv\Scripts\activate            # Windows   (Linux/Mac: source venv/bin/activate)
pip install -r requirements-dev.txt
copy .env.example .env           # then edit .env (never commit it)
python run.py                    # http://localhost:5000
```

* First start creates the database and an `admin` user with a **random password printed once in the console**.
* **Never start the app against a copy of the live `.env`**: the background jobs would send real e-mails.
  For experiments use a copy of the database, and blank `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_SERVER`.

### Run the tests (do this before every change)

```bash
python -m pytest
```

57+ tests, about 10 seconds, no real database or e-mail touched. **All must pass before you push.**

---

## 4. Configuration (`.env`)

Copy `.env.example`. Important keys (values stay private):

| Key | Meaning |
|---|---|
| `FLASK_SECRET_KEY` | Signs login cookies. **Must be set and must stay the same.** Without it a random key is used and everyone is logged out at every restart |
| `DATABASE_URL` | Database location (SQLite file by default) |
| `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER` | Outgoing e-mail |
| `MAIL_TLS_VERIFY` | Default `True` (verifies the mail server certificate). Set `False` only if the mail server certificate breaks |
| `BASE_URL` | Public address, used in e-mail links; `https://` also turns on secure cookies |
| `COMPANY_NAME` | Shown on pages and e-mails |
| `PUSHPAK_*` | Pushpak Courier API settings |

---

## 5. How a change reaches production

Full steps in [RELEASE.md](RELEASE.md). Short version:

1. Work on a branch. Run `python -m pytest`.
2. Open a pull request into `main`. CI ("Tests") runs on GitHub.
3. Merge when green. **The server pulls `main` by itself every 5 minutes**, installs changed requirements,
   restarts `courier.service`, checks `/login`, and **rolls back automatically** if it does not return 200.
4. Expect **a 502 page for about 20-60 seconds** during the restart. This is normal.
5. Confirm the live version: open `https://laxmidaak.lifc.in/healthz`. It shows `{"status":"ok","commit":"<id>"}`.
   The commit must equal the one you merged. The "Verify production deploy" workflow does this check for you.
6. Judge the change only after the new commit shows in `/healthz` (allow 5-6 minutes after merging).

**GitHub Actions needs working billing.** If CI fails instantly with "recent account payments have failed or
your spending limit needs to be increased", it is an account billing problem, not a code problem (a public repo
does not avoid it). Until fixed, run `python -m pytest` yourself before merging.

### Rollback

On GitHub open the merged PR -> **Revert** -> merge the revert. Or on the server:
`git log --oneline -5`, `git reset --hard <good-commit>`, `sudo systemctl restart courier.service`.

---

## 6. Business rules you must not break

These were fixed after real problems. Each has a test in `tests/`.

### Who sees which parcels (`app/models/parcel.py`, `get_user_parcel_filter`)

* **Admin**: everything.
* **Everybody else** sees only parcels that are:
  * created by their own login ("sent by" means created by the login, nothing else), or
  * addressed to them (their exact e-mail or exact name is the receiver), or
  * physically handled by them (they scanned it as received / out for delivery / delivered / failed / returned), or
  * (Department users) addressed to their department.
* **DO that is the only login of its branch** also sees every parcel sent from, addressed to or held at the branch.
  In a *shared* branch (several logins, e.g. Jaipur HO) these branch-wide rules are switched off, so staff do not
  see each other's parcels.
* Not matched on purpose: sender name, sender e-mail (they hold the branch name / a shared mailbox) and first-name
  prefixes. Matching them made whole branches see each other's parcels.
* Opening a tracking link (QR page) does **not** give access.
* Only the **creator or admin** can edit, archive or delete a parcel.
* The same rule drives: All Parcels, Overdue, Archive, dashboards, sidebar badges, reports, Excel export, search, detail page.

### Archive rule (`status` and `is_archived` must agree)

* Delivered parcels are archived automatically and are **hidden from All Parcels** (they live in **Archive**).
* A parcel that is still in progress can never stay archived: setting its status to `pending`, `in_transit`,
  `picked_up`, `query_raised` or `delivered_pending` un-archives it automatically (model validator), and the server
  repairs old inconsistent rows at startup. (Symptom if this ever breaks: the scanner finds a parcel that All Parcels
  does not list.)

### "Delivered Today"

* Counted from midnight **India time** (`app/utils.py: ist_today_start`), archived parcels included.
* The card opens `/dispatch/list?filter=delivered_today`, which uses the same rule, so card and list match.

### Scanning (`app/routes/scan.py`)

* Allowed actions: received, out_for_delivery, delivered, failed, returned.
* Any branch may log received / out for delivery. delivered / failed / returned need the parcel to be in the user's scope;
  delivered needs the destination branch (or admin).
* Parcels in `query_raised` or `closed` cannot be changed by scanning (only by admin).

### Permissions (Accounts -> Edit)

Flags: `can_scan`, `can_raise_query`, `can_dispatch_queries`, `can_new_dispatch`, `can_bulk_dispatch`,
`can_view_parcels`, `can_overdue`, `can_archive`, `can_billing_rates`, `can_reports`.

* An account with **no saved flags** uses defaults: everything on, except that **Department users have New Dispatch and
  Bulk Dispatch off**.
* Saving the Edit form saves *every* tick box. The form is pre-filled with the account's real permissions so an edit does
  not switch things off by accident.
* The **New Dispatch button** and sidebar link appear only when `can_new_dispatch` is on. Without it `/dispatch/new` shows a
  friendly "You don't have permission" page (403).

### Passwords

* Passwords are stored only as bcrypt hashes. **They cannot be shown or recovered.** Do not add a feature that stores a
  readable or reversible copy.
* To give someone a new password: Accounts -> **Pass** button on their row -> type the new password -> hand it over.
* Users choose their own password in Profile / Forgot password (minimum 8 characters).
* Bulk Excel import creates default passwords from a documented pattern. **Ask every imported account to change its
  password on first login**, and re-check the import service before the repo is made public.
* Login lockout: 5 wrong attempts lock that username for 3 minutes (kept in memory, resets on restart).

---

## 7. Keeping it running regularly (operations checklist)

**Daily / weekly**
* Open `/healthz` and `/login`: both should answer fast.
* Take a database backup (the live database is the most valuable file). Safe online copy:
  ```bash
  sqlite3 /path/to/courier_tracker.db ".backup '/home/ubuntu/backups/courier_$(date +%Y%m%d).db'"
  ```
  Keep at least 14 days, copy one weekly backup off the server. **Test a restore once.**
* Check disk space (`df -h`): `app/static/uploads` and `app/static/qr` grow with every parcel.

**On the server**
```bash
sudo systemctl status courier.service
sudo journalctl -u courier.service -n 100          # app errors
systemctl list-timers courier-autoupdate.timer     # next auto-deploy
sudo journalctl -u courier-autoupdate.service -n 50
sudo systemctl start courier-autoupdate.service    # deploy right now
```
Never edit files on the server by hand: the auto-update uses fast-forward only and stops if the server copy differs.

**Monthly**
* Review Security Logs (Admin menu) for failed logins and password resets.
* Update dependencies one at a time, with the tests green, never together with a feature change.
* Check that the SMTP password and Pushpak credentials still work (send a test mail).

**Secrets**
* `.env`, `*.db`, `*.pem` are in `.gitignore`; CI fails if any is committed.
* The SSH key, GitHub secrets and `.env` are the keys to production. Store them in a password manager, not in chat or files.

---

## 8. Troubleshooting (symptom -> cause -> action)

| Symptom | Likely cause | What to do |
|---|---|---|
| **502 Bad Gateway** for under a minute | Normal restart right after a deploy | Wait, refresh |
| 502 that does not go away | App crashed | `journalctl -u courier.service -n 100`; last-resort rollback (section 5) |
| Change not visible after merge | Server pulls every 5 min | Check `/healthz` commit; hard refresh (Ctrl+F5) |
| **403 Forbidden** / "You don't have permission" | The login lacks that permission, or the parcel is outside its scope | Accounts -> Edit -> tick the permission |
| New Dispatch button missing | `can_new_dispatch` is off, or the user is a Department login | Accounts -> Edit |
| Parcel loads in Scanner but not in All Parcels | Archived while in progress (old bug, now auto-repaired), or not in that user's scope | Check Archive; check who created / received it |
| "Delivered Today" card number and list differ | Old links filtered by status only | Fixed; card opens `filter=delivered_today` |
| Branch user sees nobody else's parcels | Intended (scope rules, section 6) | - |
| Everyone logged out after restart | `FLASK_SECRET_KEY` missing or changed | Set it once in `.env` and keep it |
| Users logged out when changing browser | Session is tied to the browser (User-Agent) | Normal |
| E-mails not arriving | SMTP settings / certificate | Check `.env`, `journalctl`, `MAIL_TLS_VERIFY` |
| GitHub Actions red instantly | Account billing | Fix billing; run tests locally meanwhile |
| Database locked | Two processes writing SQLite | Restart `courier.service`; avoid running scripts on the live file |

---

## 9. Tips and tricks that saved time

* **Test on a copy.** Copy the database, point `DATABASE_URL` at the copy, blank the mail settings, then experiment.
* **Verify from a fresh clone.** `git clone` the branch into an empty folder and run `python -m pytest` there. This once
  revealed that `.gitignore` (`test_*.py`) had silently kept the test files out of Git.
* **Check what Git will commit** (`git status`) before `git add`. Test runs can create QR images in `app/static/qr/`.
* Small pull requests, one subject each, with a test that fails without the fix.
* Windows shows "LF will be replaced by CRLF" warnings: harmless. Shell scripts in `deploy/` must stay LF.
* After merging, **wait for the commit in `/healthz`** before saying "it did not work".
* Use the repo public only while shipping (free CI minutes), then make it private again. While public, anyone can read the code.
* Heavy pages: `inject_globals` in `app/__init__.py` runs several queries on every page. Optimise with care and tests.
* Dates are stored in UTC; "today" for the business is India time (`ist_today_start`).
* The service worker / PWA is intentionally **not** active (it would cache private pages).

---

## 10. Working with AI assistants (any model: Claude, GPT, Gemini, ...)

How to get reliable results from whichever model you use:

1. **Start with context.** Tell the model to read `Handover.md`, `RELEASE.md` and `README.md` first, then the files it will touch.
2. **State the goal and the limits** in plain words: "fix X, change nothing else, do not deploy until I say deploy".
3. **Make it prove the fix**: reproduce the problem in a test, make the test pass, run the **whole** suite, show the result.
4. **One branch, one purpose.** Ask for a branch and a pull request, not direct edits to `main`.
5. **Keep the human decision points**: deploying, merging, deleting data, changing permissions, anything that touches live data.
6. **Give real examples**: the exact page, the login role (Admin / DO / Department), the tracking number, a screenshot, the error text.
   Most "bugs" here were permission or scope questions, which need the role and the page.
7. **Ask the model to verify after deploy**: read `/healthz`, wait out the 502 window, then re-check.
8. **Never paste secrets** (`.env`, keys, passwords) into any AI chat. Use placeholders.
9. **Safety limits are real.** Some assistants refuse to store readable passwords or run destructive Git commands (force-push,
   history rewrite). Use the safe alternative (reset password; add a new commit) instead of arguing.
10. **Models differ**: smaller / faster models are fine for text, labels and small fixes; use the strongest model for
    permission rules, data migrations and anything touching the database. Always re-run the tests whichever model wrote the code.

Starter prompt you can reuse:

```text
You are working on the Laxmi Daak Flask app. First read Handover.md, RELEASE.md and README.md.
Task: <what is wrong, which page, which role (Admin/DO/Department), example tracking number>.
Rules: create a branch; write a failing test first; fix; run `python -m pytest` (all must pass);
do not touch .env or any .db file; do not push to main or deploy until I say "deploy";
at the end tell me what changed, what you could not check, and how I can verify it.
```

---

## 11. Known limitations and ideas for later

* `archive-guard` branch (a model validator that keeps status and archive flag in sync) exists but is **not** merged; the
  scan fix plus startup repair already cover the known cases. Merge it for extra safety.
* Login lockout is per process and in memory; a proper limiter needs the proxy IP headers configured.
* Several pages run many queries per request; add caching / indexes if the data grows.
* `AWS_DEPLOYMENT.md` describes an older Elastic Beanstalk route; production actually runs on EC2 + systemd + nginx.
* Deploys cause a short 502. A reload-style restart (gunicorn HUP / two workers) would remove it.
* The All Parcels list shows the dispatch date only; a "Delivered on" column would help delivered parcels.
* SQLite is fine for this size; plan a move to PostgreSQL (RDS) if several people write at the same moment all day.

---

## 12. People and accounts (fill in privately)

Keep the real values in a password manager, not here.

| What | Where it is kept |
|---|---|
| GitHub owner / admin | `<name>` |
| AWS account / EC2 access | `<name>`, key file stored at `<private location>` |
| Domain / nginx / SSL | `<name>` |
| SMTP mailbox | `<name>` |
| Pushpak courier account | `<name>` |
| Admin logins of the app | `<names>` |
