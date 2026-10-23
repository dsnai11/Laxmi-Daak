# Release process: GitHub (test) -> EC2 (production)

Nothing reaches production without passing the tests on GitHub first.

```
 feature branch --PR--> CI tests --green--> merge to main --> EC2 pulls main (<=5 min)
                                                                  |
                          Verify production deploy (green) <------+   auto rollback if /login != 200
```

## Every release, step by step

1. **Make the repo public** (Settings -> General -> Danger Zone -> Change visibility).
   Public repos get unlimited free Actions minutes; private repos only get 2,000 per month.
2. **Create a branch** and push your change:
   ```bash
   git checkout -b my-change
   git add -A && git commit -m "Describe the change"
   git push -u origin my-change
   ```
3. **Open a pull request** into `main` (GitHub shows a "Compare & pull request" button).
   The **CI / Tests** check starts by itself.
4. **Merge only when Tests is green.** Red = do not merge; fix and push to the same branch.
5. After the merge the server pulls `main` within about 5 minutes, installs new requirements,
   restarts `courier.service` and checks `/login`. If the app is unhealthy it rolls back by itself.
6. Open **Actions -> Verify production deploy**. When it is green, the live site is running your
   exact commit (`https://<your-domain>/healthz` shows the commit id).
7. **Make the repo private again.**

## Rules that keep production safe

- Never push straight to `main`. Turn on branch protection (below) so GitHub enforces this.
- Never commit `.env`, `*.db`, `*.pem`. CI fails if they are tracked.
- Database changes must work on the live data: new columns nullable or with a default.
- Do not edit files on the server by hand: the auto-update uses fast-forward only and stops if
  the server copy differs.

## One-time GitHub settings (repo owner)

Settings -> Rules -> Rulesets -> New branch ruleset, target `main`:
- Require a pull request before merging
- Require status checks to pass: **Tests**
- Block force pushes and deletions

(Rulesets are available for free on public repos, which fits the public-while-releasing plan.
 They are not enforced while the repo is private on the free plan.)

Optional: Settings -> Secrets and variables -> Actions -> Variables -> `LIVE_URL`
to point the deploy check at a different domain.

## Rollback

Fastest: on GitHub open the merged PR -> **Revert** -> merge the revert PR. The server deploys
the revert in about 5 minutes. Emergency (on the server):

```bash
cd /home/ubuntu/courier_app/courier_tracker
git log --oneline -5
git reset --hard <previous-good-commit> && sudo systemctl restart courier.service
```

## Useful server commands

```bash
systemctl list-timers courier-autoupdate.timer
sudo systemctl start courier-autoupdate.service       # deploy right now
journalctl -u courier-autoupdate.service -n 50
journalctl -u courier.service -n 100
```

## Heads-up while the repo is public

Everything in the repository is readable by anyone, including how the bulk import builds default
branch passwords. Keep the public window as short as possible, and never commit real data.
