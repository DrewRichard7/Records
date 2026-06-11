# Gmail SMTP setup

Records can send password reset emails through Gmail SMTP. Gmail does not let most apps use your normal Google account password for SMTP. Use a Google app password instead.

These instructions assume:

- Records is running on a Raspberry Pi as the `pi` user.
- Records is managed by `/etc/systemd/system/records.service`.
- Records is reachable through Tailscale HTTPS, for example `https://raspberrypi.<tailnet-name>.ts.net`.
- You have access to the Gmail or Google Workspace account you want to send from.

## 1. Enable 2-Step Verification

Open your Google Account security page:

https://myaccount.google.com/security

Under `How you sign in to Google`, enable `2-Step Verification`.

Google requires 2-Step Verification before it will let you create app passwords for most accounts.

## 2. Create a Gmail app password

Open:

https://myaccount.google.com/apppasswords

Create an app password for Records.

Suggested labels:

- App: `Mail`
- Device/name: `Records Raspberry Pi`

Google will show a 16-character app password. Copy it immediately. It is usually displayed with spaces for readability, but you can store it without spaces in the systemd service.

Do not use your normal Google password in Records. Use this app password.

## 3. Edit the Records systemd service

Open the service file:

```bash
sudo nano /etc/systemd/system/records.service
```

Add these lines under `[Service]`, replacing the placeholders:

```ini
Environment=RECORDS_RECOVERY_EMAIL=youraddress@gmail.com
Environment=RECORDS_PUBLIC_URL=https://raspberrypi.<tailnet-name>.ts.net
Environment=RECORDS_SMTP_HOST=smtp.gmail.com
Environment=RECORDS_SMTP_PORT=587
Environment=RECORDS_SMTP_USERNAME=youraddress@gmail.com
Environment=RECORDS_SMTP_PASSWORD=your-gmail-app-password
Environment=RECORDS_SMTP_FROM_EMAIL=youraddress@gmail.com
```

Keep these existing auth settings too:

```ini
Environment=RECORDS_PASSWORD_HASH=pbkdf2_sha256$...
Environment=RECORDS_SESSION_SECRET=long-random-secret
Environment=RECORDS_COOKIE_SECURE=1
```

Use `RECORDS_COOKIE_SECURE=1` only if you open Records through HTTPS, such as Tailscale Serve. If you open Records through plain `http://100.x.y.z:8000`, omit `RECORDS_COOKIE_SECURE=1`.

## 4. Restart Records

Reload systemd and restart the app:

```bash
sudo systemctl daemon-reload
sudo systemctl restart records.service
sudo systemctl status records.service
```

Check logs if the service does not start:

```bash
journalctl -u records.service -n 100 --no-pager
```

## 5. Test password reset

1. Open Records in your browser.
2. Go to `Forgot your password?`.
3. Enter the exact email address from `RECORDS_RECOVERY_EMAIL`.
4. Submit the form.
5. Check Gmail for the reset email.
6. Open the reset link and set a new password.

The forgot-password page intentionally gives a generic response. If you type a different email address, it will not say that the address is wrong.

## Troubleshooting

If no email arrives:

- Confirm `RECORDS_RECOVERY_EMAIL` exactly matches what you typed into the forgot-password form.
- Confirm `RECORDS_SMTP_USERNAME` is the Gmail address.
- Confirm `RECORDS_SMTP_PASSWORD` is the Google app password, not your normal Google password.
- Confirm `RECORDS_SMTP_HOST=smtp.gmail.com`.
- Confirm `RECORDS_SMTP_PORT=587`.
- Confirm `RECORDS_PUBLIC_URL` is the Tailscale HTTPS URL you actually use from your phone.
- Check spam and all-mail folders.
- Check Records logs with `journalctl -u records.service -n 100 --no-pager`.

If Google rejects login:

- Make sure 2-Step Verification is enabled.
- Create a fresh app password and replace `RECORDS_SMTP_PASSWORD`.
- If this is a Google Workspace account, your workspace admin may need to allow app passwords.

If the reset link opens but login does not stick:

- If using HTTPS, keep `RECORDS_COOKIE_SECURE=1`.
- If using plain HTTP, remove `RECORDS_COOKIE_SECURE=1`.
- Restart Records after changing the service file.
