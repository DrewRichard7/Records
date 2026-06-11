# Proton Mail SMTP setup

Records can send password reset email through Proton Mail, but not by connecting directly to a public Proton SMTP server with your normal Proton password. Proton's supported SMTP path is Proton Mail Bridge, which runs locally and exposes SMTP credentials for apps. Proton's Linux Bridge docs state that Bridge integrates Proton Mail with IMAP/SMTP email programs and is available to paid Proton Mail users:

- https://proton.me/support/bridge-for-linux
- https://proton.me/support/protonmail-bridge-install

These instructions assume:

- You have a paid Proton Mail account.
- Records is running on a Raspberry Pi as the `pi` user.
- Records is reachable through Tailscale HTTPS, for example `https://raspberrypi.<tailnet-name>.ts.net`.

## Raspberry Pi architecture check

Before downloading Bridge, check the Pi architecture:

```bash
uname -m
dpkg --print-architecture
```

Do not install an `amd64` package on a Raspberry Pi. `amd64` is for Intel/AMD x86_64 machines, not ARM Raspberry Pi boards. A Pi Zero 2 W usually reports an ARM architecture such as `armhf`, `arm64`, or `aarch64`.

If Proton does not provide a Bridge package for your exact Pi architecture, Bridge cannot be installed directly on that Pi with apt. In that case, use one of these options:

- Use Gmail, Fastmail, or another SMTP provider just for Records password reset emails.
- Run Proton Mail Bridge on an always-on x86_64 Linux machine instead of the Pi.
- Skip email reset and reset the password manually over SSH by generating a new `RECORDS_PASSWORD_HASH` and restarting `records.service`.

## 1. Install Proton Mail Bridge

Follow Proton's Linux install instructions for your Raspberry Pi OS:

https://proton.me/support/bridge-for-linux

Proton provides packages for common Linux families. On Raspberry Pi OS, use the Debian/Ubuntu-style instructions only if your Pi OS architecture is supported by Proton's package.

Proton notes that Linux Bridge needs a secret-service password manager such as GNOME Keyring or `pass`. On a headless Pi, `pass` is usually the more practical route. Follow Proton's current instructions if their package prompts you for this during setup.

## 2. Sign into Bridge on the Pi

Start Proton Mail Bridge and sign into your Proton account.

Bridge will generate local mail-client credentials. These are not your Proton login password. Copy the SMTP values shown by Bridge:

- SMTP host, usually `127.0.0.1` or `localhost`
- SMTP port
- Bridge-generated username
- Bridge-generated password
- Sending email address

Keep Bridge running on the Pi. Records sends reset email by connecting to this local Bridge SMTP service.

## 3. Configure Records

Edit the systemd service:

```bash
sudo nano /etc/systemd/system/records.service
```

Add these lines under `[Service]`, replacing placeholders with the exact values shown by Bridge:

```ini
Environment=RECORDS_RECOVERY_EMAIL=you@proton.me
Environment=RECORDS_PUBLIC_URL=https://raspberrypi.<tailnet-name>.ts.net
Environment=RECORDS_SMTP_HOST=127.0.0.1
Environment=RECORDS_SMTP_PORT=<bridge-smtp-port>
Environment=RECORDS_SMTP_USERNAME=<bridge-generated-username>
Environment=RECORDS_SMTP_PASSWORD=<bridge-generated-password>
Environment=RECORDS_SMTP_FROM_EMAIL=you@proton.me
Environment=RECORDS_SMTP_TLS=1
Environment=RECORDS_SMTP_VERIFY_TLS=0
```

`RECORDS_SMTP_VERIFY_TLS=0` is for local Proton Bridge only. Bridge commonly uses a local certificate that Python cannot verify with the normal public certificate store. Do not use this setting for a remote SMTP provider.

If your Bridge screen says SMTP security is disabled/plain on localhost, use this instead:

```ini
Environment=RECORDS_SMTP_TLS=0
```

and omit `RECORDS_SMTP_VERIFY_TLS`.

## 4. Restart Records

```bash
sudo systemctl daemon-reload
sudo systemctl restart records.service
sudo systemctl status records.service
```

Then open Records, go to `Forgot your password?`, enter the configured `RECORDS_RECOVERY_EMAIL`, and confirm a reset email arrives.

## Troubleshooting

Check Records logs:

```bash
journalctl -u records.service -n 100 --no-pager
```

If no email is sent:

- Confirm Proton Mail Bridge is running on the Pi.
- Confirm the SMTP host and port match Bridge exactly.
- Confirm the username and password are Bridge-generated values, not your Proton password.
- Confirm `RECORDS_PUBLIC_URL` is the Tailscale HTTPS URL you open from your phone.
- Confirm `RECORDS_RECOVERY_EMAIL` exactly matches the email address you type into the forgot-password form.
