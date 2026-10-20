# Server-side auto deploy

The EC2 server checks GitHub every 5 minutes. When `main` has new commits it pulls them,
installs requirements if they changed, restarts `courier.service`, and checks that `/login`
returns 200. If the app doesn't come up, it rolls back to the previous commit.

## One-time install (on the server)

The server must be able to `git fetch` from GitHub (deploy key added under repo
Settings → Deploy keys).

```bash
cd /home/ubuntu/courier_app/courier_tracker
sudo -u ubuntu git pull --ff-only origin main
sudo cp deploy/courier-autoupdate.service deploy/courier-autoupdate.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now courier-autoupdate.timer
```

## Useful commands

```bash
systemctl list-timers courier-autoupdate.timer      # when it runs next
sudo systemctl start courier-autoupdate.service     # check for updates right now
journalctl -u courier-autoupdate.service -n 50      # what it did
sudo systemctl disable --now courier-autoupdate.timer   # turn auto-update off
```
