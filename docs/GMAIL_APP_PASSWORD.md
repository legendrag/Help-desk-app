# Gmail App Password Setup (Admin)

Use this for `Email Settings` in admin panel.

## Steps
1. Log into the Gmail account that will send notifications.
2. Enable **2-Step Verification** on the Google account.
3. Open Google Account settings -> **Security** -> **App passwords**.
4. Create a new app password (16 chars).
5. In DeskPlus Admin -> Email Settings, fill:
   - SMTP Host: `smtp.gmail.com`
   - SMTP Port: `587`
   - Encryption: `tls`
   - SMTP Email: your Gmail address
   - SMTP Password: generated app password
   - From Name / From Email: sender identity
6. Save as active config.

## Troubleshooting
- Authentication failed: verify app password and 2FA is enabled.
- Timeout: check firewall allows outbound SMTP to `smtp.gmail.com:587`.
- No emails received: inspect backend logs for retry errors.
