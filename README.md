# Climatix IC — Home Assistant integration

Pulls temperatures, pump states and other datapoints from a Siemens **Climatix IC**
heating plant into Home Assistant. No cloud broker, no Docker, no YAML — add it from
the UI, enter your account, and the plant's datapoints show up as entities.

It logs in to the Climatix IC cloud the same way the web UI does (Azure AD B2C +
authenticator TOTP), auto-discovers every datapoint on the plant's web overview page,
and polls their values. Entity names, units and types come straight from Climatix.

## Install (HACS)

1. HACS → ⋮ → **Custom repositories** → add `https://github.com/rpodgorny/hass-climatix-ic`, category **Integration**.
2. Install **Climatix IC**, then restart Home Assistant.
3. **Settings → Devices & Services → Add Integration → Climatix IC.**

## Configure

You need three things:

| Field | What it is |
|-------|-----------|
| **Email** | your Climatix IC login |
| **Password** | your Climatix IC password |
| **TOTP secret** | the **base32 secret** behind your authenticator app's QR code — *not* the 6-digit code |

If your account has more than one plant you'll be asked to pick one; a single plant is
selected automatically.

### Getting the TOTP secret

Climatix IC enforces two-factor authentication, so the integration needs the *secret*
that generates the 6-digit codes (it computes the codes itself). The secret is a base32
string — letters `A–Z` and digits `2–7`, e.g. `JBSWY3DPEHPK3PXP`.

**Easiest — grab it when you set 2FA up.** On the "scan this QR code" screen there's
almost always a *"can't scan?"* / *"enter setup key manually"* link. The key it shows
**is** the base32 secret. Copy it. Done.

**Already set up? Convert the QR.** You need the QR's underlying text, then convert it:

1. Get the QR text:
   - *Setup QR* — if you still have the original 2FA setup QR, scan it with any QR-reader
     app. The text looks like `otpauth://totp/...?secret=XXXX&issuer=...`.
   - *Already only on your phone* — in **Google Authenticator** choose **Transfer
     accounts → Export**, pick the Climatix account, and scan the QR it shows with a QR
     reader. The text looks like `otpauth-migration://offline?data=...`.
2. Convert it with the bundled helper (Python 3, standard library only, fully offline):

   ```
   python3 tools/totp_secret.py 'otpauth://totp/...?secret=...'
   python3 tools/totp_secret.py 'otpauth-migration://offline?data=...'
   ```

   It prints `account: SECRET`. Use `SECRET` in the integration's **TOTP secret** field.

   - `otpauth://` already contains a base32 secret — the tool just extracts it.
   - `otpauth-migration://` (the Google Authenticator export) stores the secret as raw
     bytes; the tool base32-encodes it for you.

Store the secret somewhere safe; Home Assistant keeps it encrypted in the config entry.
Don't paste it into untrusted websites — it's the full second factor.

## Options

**Configure** on the integration lets you change the **poll interval** (default 120 s).

## Notes & limitations

- **Read-only.** Sensors and binary sensors only; it does not write setpoints (yet).
- **Cloud polling.** Each poll re-reads every datapoint over the Climatix cloud; keep
  the interval reasonable. The session is reused and only re-established when it expires.
- Datapoint captions from Climatix are not unique (e.g. two boilers both report
  *"Boiler temp actual value"*); such entities get the datapoint id appended to their name.

## Disclaimer

Unofficial, not affiliated with Siemens. Uses the same private cloud endpoints as the
Climatix IC web app, which may change without notice.
