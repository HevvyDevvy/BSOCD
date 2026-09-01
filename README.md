# Basic SOC Drills v5 — Desktop GUI

A themed, cross-platform desktop app for the SOC analyst drill toolkit that
used to be a headless CLI/GTK script. Rebuilt on **Tkinter** (ships with
Python, no GTK/system dev libraries required) with a UI styled after the
crest artwork: gunmetal background, radar green, and warning orange.

## What changed from the old CLI/GTK version

- **Real GUI, not a blank label.** Every drill from the old script is now a
  card you click, with proper inputs instead of hard-coded values.
- **Simulation Mode (on by default).** Every action can be previewed
  ("Would run: ...") before it touches the system. Flip the switch in the
  top bar only when you're ready to execute for real.
- **No more dead background threads.** The old script spun up five infinite
  loops whose trigger conditions were hard-coded to `False`, so they never
  actually did anything. Those are gone; every action is now explicit and
  user-triggered, plus a real Suricata start/stop control and a read-only
  alert tail.
- **No hard-coded credentials.** `add_user()` now asks for a password in a
  masked field and pipes it into `chpasswd` — it never appears on the
  command line, in shell history, or in the on-screen log.
- **Confirmations for destructive actions** — deleting a user, restarting a
  service, quarantining an IP, changing a MAC address, and clearing caches
  all ask "are you sure?" before running (skipped automatically while
  Simulation Mode is on).
- **Graceful degradation.** If a tool (nmap, suricata, lynis, ufw, ...)
  isn't installed, the app tells you instead of crashing. An "Overview" tab
  shows a live checklist of what's installed on your system.
- **Input validation** on IPs, usernames, and service names — arguments are
  always passed as a list to `subprocess`, never through a shell, so there's
  no shell-injection surface even from typed input.
- **Fixed a couple of broken commands** from the original script:
  `ausearch -sc user_login` (invalid flag/value pair) is now
  `ausearch -m USER_LOGIN`; `journalctl -e` (an interactive pager that would
  hang headless) is now `journalctl -n <N> --no-pager`; `lynis audit system`
  now runs with `--quiet` so it doesn't block waiting for a keypress.

## Requirements

```bash
# Python 3.9+ with Tkinter (Tkinter ships with Python on most systems;
# on Debian/Kali/Ubuntu it's a separate package):
sudo apt update
sudo apt install -y python3 python3-tk
```

No other Python packages are required — the app uses only the standard
library (`tkinter`, `subprocess`, `threading`, `queue`).

### Optional: the underlying security tools

The app runs happily with none of these installed — it'll just report each
drill's tool as missing until you add it. Install what you actually use:

```bash
sudo apt install -y clamav nmap macchanger logrotate suricata lynis \
                     ufw rsync curl audit
sudo freshclam            # seed ClamAV definitions
sudo suricata-update      # pull Suricata rule sets
```

`ossec-logtest` comes from an OSSEC/Wazuh HIDS install if you use one; the
card for it will simply report "not installed" otherwise.

## Running it

```bash
cd BasicSOCDrills
python3 app.py
```

Leave **Simulation Mode** on the first time you open it and click through
the cards to see exactly what each one would run. Turn it off in the top
bar once you're ready to execute for real — most actions call `sudo`
internally and will prompt for your password in the terminal you launched
the app from.

## Project layout

```
app.py                     entry point (shows the privilege-notice dialog first)
soc_drills/
  consent.py                 first-run privilege/consent warning dialog
  platform_backend.py        picks backend.py (Linux/macOS) or backend_windows.py (Windows)
  backend.py                  Linux/macOS drills (sudo, systemctl, ufw, ...)
  backend_windows.py          Windows drills (UAC-scoped, netsh/NetAdapter/wevtutil, ...)
  gui.py                      window, sidebar, cards, dialogs
  console.py                  thread-safe live log widget
  theme.py                    colors / ttk styling matching the crest logo
packaging/
  BasicSOCDrills.spec         PyInstaller spec (Windows .exe)
  AppxManifest.xml            MSIX/APPX manifest template
  build_msix.ps1              exe -> .msix/.appx/.msixbundle/.appxbundle
  icons/                      Store logo assets generated from the crest artwork
.github/workflows/
  build.yml                    unsigned build + package on every push (CI)
  release.yml                  signed build + GitHub Release on version tag
PRIVACY_POLICY.md            draft privacy policy for the Store listing
```

## Getting this onto GitHub

```bash
cd BasicSOCDrills
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

That's it - `.github/workflows/build.yml` picks up automatically. Every
push triggers a Windows build and packages unsigned `.msix` / `.appx` /
`.msixbundle` / `.appxbundle` files, downloadable from that commit's
**Actions** tab under **Artifacts**.

### Code signing (for a real Store submission)

1. Obtain a code-signing certificate as a `.pfx` (EV cert recommended for
   Store submission; a self-signed cert is fine for local sideload
   testing only).
2. Base64-encode it on your own machine - **never commit the `.pfx`
   itself**:
   ```bash
   base64 -w 0 your_cert.pfx > cert_base64.txt
   ```
3. In GitHub: **Settings -> Secrets and variables -> Actions -> New
   repository secret**, add:
   - `CSC_LINK` - paste the contents of `cert_base64.txt`
   - `CSC_KEY_PASSWORD` - the `.pfx` password
4. Also edit `packaging/AppxManifest.xml` and set `Identity Publisher=`
   to match your certificate's Subject exactly (Store submission fails
   otherwise), and `Identity Name=` to the package name you reserved in
   Partner Center.

### Cutting a signed release

```bash
git tag v1.0.0
git push --tags
```

This triggers `release.yml`: builds, signs (if the secrets above are
set), and attaches `.exe` / `.msix` / `.appx` / `.msixbundle` /
`.appxbundle` to a new GitHub Release automatically.

### Submitting to the Microsoft Store

1. Register at [Partner Center](https://partner.microsoft.com/dashboard/registration)
   and reserve your app name - this gives you the exact `Identity Name`
   and `Publisher` values to put in `AppxManifest.xml`.
2. Download a release `.msixbundle` from a tagged GitHub Release (or
   Actions artifact) and upload it in Partner Center's submission flow.
3. Fill in the Store listing using the description drafted earlier in
   this project, and Partner Center will ask for a hosted Privacy
   Policy URL - publish `PRIVACY_POLICY.md` somewhere public (GitHub
   Pages works) and fill in its placeholders first.

## Notes on scope

This app talks to tools already on your machine (nmap, suricata, ufw,
clamav, lynis, etc.) and to your own OS (user accounts, services, firewall
rules, MAC address). It does not include the placeholder integrations the
original README mentioned (md5house, crackstation, Exploit-DB scraping,
"dark stack overflow", cloud CLIs) — those were never implemented in the
source script either. If you want one of those added, the cleanest path is
a new card in `gui.py` calling a new function in `backend.py` that shells
out to that tool's own CLI (e.g. `aws`, `az`, `gcloud`) the same way the
existing drills do.

Only run scans, quarantines, and account changes against systems and
accounts you own or are explicitly authorized to test.
