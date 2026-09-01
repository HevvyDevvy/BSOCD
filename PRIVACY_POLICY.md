# Basic SOC Drills — Privacy Policy

*Last updated: [DATE]*

## Summary

Basic SOC Drills is a local system-administration tool. It does not collect,
transmit, sell, or share any personal data, telemetry, or usage analytics.
Everything the app does happens on your own device.

## What the app accesses, and why

| Access | Purpose |
|---|---|
| Local system information (CPU, memory, disk, event logs) | Displayed to you in the app; never leaves your device |
| Network configuration (adapter list, MAC address) | Only read/changed when you run the "Randomize MAC" drill yourself |
| Local user accounts | Only created/removed when you run the "Add User" / "Remove User" drills yourself |
| Windows Firewall rules | Only added when you run the "Quarantine an IP" drill yourself |
| Password you type for a new local account | Passed directly to Windows' account-creation API as a SecureString; never written to disk, logged, or displayed on screen |
| A threat-intel feed URL you provide | Only contacted if you enter a URL and run that drill yourself — the app has no default or built-in feed |

## What we do not do

- We do not collect analytics, crash reports, or usage telemetry.
- We do not create a user account, require sign-in, or use ads.
- We do not transmit any data to the developer or any third party.
- We do not run anything automatically or in the background — every action
  requires you to open a specific card and click Run.

## Third-party tools

Some drills call external, separately-installed tools (e.g. nmap, Suricata)
if you have them installed. Those tools' own data handling is governed by
their own documentation/licenses, not this app.

## Elevated privileges

Certain drills request elevated (Administrator) permission via a standard
Windows UAC prompt, scoped to that single action. You will always see this
prompt and must approve it yourself before anything elevated runs. A
one-time notice explaining this appears the first time you launch the app.

## Changes to this policy

If this policy changes, the updated version will be included with the next
app update and posted at [YOUR PRIVACY POLICY URL].

## Contact

Questions about this policy: [YOUR CONTACT EMAIL]
