## What changed and why

## Checklist
- [ ] CI is green (Tests)
- [ ] No `.env`, database, key or password in the diff
- [ ] Database changes are safe for the live data (new columns nullable / have defaults)
- [ ] I know how to roll back (revert this PR)

After merging: the server deploys within ~5 minutes and **Verify production deploy** turns green.
Only then make the repo private again.
