# MBBB contact form

Status: agreed design — not yet implemented.

Last updated: 21 October 2026.

## Purpose

Replace the website's current `mailto:` form with a server-side handler so visitors can submit enquiries without opening an email application. Keep the implementation small and make the email settings easy to change for production.

## Hosting and implementation

- Demo website: https://mbbb.dcsmail.uk
- Hosting: Mythic Beasts VPS, Ubuntu 24.04, with Caddy.
- Website document root: `/srv/www/mbbb/`.
- A small Python handler will validate submissions and send email using Python's built-in SMTP support.
- No database or additional email service is required.
- Browser JavaScript will submit to the same-origin relative endpoint `/api/contact`.
- Caddy will forward that endpoint to the handler, which will listen on loopback only. The local port is still to be selected.
- A systemd service will run the handler under an unprivileged account and restart it when necessary.

The production hosting arrangement has not yet been decided. This design can move to another host that supports the same endpoint and a server-side process. Static-only hosting would require a different backend arrangement.

## Demo email behaviour

Use the existing dedicated Mythic Beasts mailbox for both sending and receiving demo enquiries:

```text
From: MBBB Website <mbbb@dcsmail.uk>
To: mbbb@dcsmail.uk
Reply-To: the visitor's validated email address
Subject prefix: MBBB Demo Enquiry
```

Do not send demo enquiries to the band's production enquiries address. The recipient and sender must come from server configuration, not browser-submitted fields.

## Proposed VPS files

| File | Purpose |
| --- | --- |
| `/opt/mbbb-contact/contact.py` | Python form handler |
| `/etc/mbbb-contact.env` | Private email configuration |
| `/etc/systemd/system/mbbb-contact.service` | Service definition |

These paths are outside the static website root and therefore outside its current `rsync --delete` deployment target. The handler and its service will need a separate installation/update step.

## Email configuration

Proposed contents of `/etc/mbbb-contact.env`:

```ini
SMTP_HOST=smtp-auth.mythic-beasts.com
SMTP_PORT=587
SMTP_USERNAME=mbbb@dcsmail.uk
SMTP_PASSWORD=replace-with-mailbox-password

MAIL_FROM=mbbb@dcsmail.uk
MAIL_TO=mbbb@dcsmail.uk
MAIL_SUBJECT_PREFIX=MBBB Demo Enquiry
```

The service will load this file using systemd's `EnvironmentFile` setting. The Python handler will read the resulting environment variables. Use systemd-compatible quoting for values where needed; this is not a shell script.

SMTP uses STARTTLS with certificate verification. The authenticated mailbox must be authorised to send from the configured From address.

Keep the real configuration outside GitHub and the web root. Restrict access, for example by making it root-owned with mode `0600` when systemd loads it. Never put the password in HTML, browser JavaScript, logs or this README. A placeholder-only configuration example may be kept in the repository.

Mythic Beasts documentation:

- SMTP settings: https://www.mythic-beasts.com/support/hosting/mail/client
- Sender restrictions: https://www.mythic-beasts.com/support/hosting/mail/sender-restrictions

## Form behaviour

Retain the existing enquiry fields: first name, last name, email address, event date, event type and message.

The planned handler will:

- Validate required fields and email addresses on the server.
- Limit request and field sizes and reject invalid input.
- Check a hidden honeypot field and apply basic rate limiting.
- Send plain-text email through the configured SMTP server with a finite timeout.
- Return a clear success or error response without exposing credentials or internal exceptions.
- Avoid logging enquiry bodies or other unnecessary personal information.

The browser will prevent duplicate submissions while a request is in progress. It will show success only after SMTP accepts the message. SMTP acceptance does not guarantee final inbox delivery.

On failure, preserve the entered details and offer an email link. Keep a visible direct-contact option for visitors who cannot use the scripted form.

There is no planned persistent message queue. A failed submission will need to be retried by the visitor.

## Switching to production

1. Confirm production hosting supports the handler and `/api/contact` route.
2. Choose the production sending mailbox and receiving address.
3. Update SMTP credentials, sender, recipient and subject prefix in the private configuration file.
4. Check sender authorisation and the sending domain's email authentication configuration.
5. Restart `mbbb-contact.service` to load the new settings.
6. Test a submission, delivery to the correct inbox and Reply-To behaviour.
7. Update any visible demo contact links and the privacy notice to match the production arrangements.

The browser endpoint remains `/api/contact`, so no hostname or SMTP credentials need to be embedded in the JavaScript.

## Implementation checklist

- [ ] Create the Python handler.
- [ ] Install the private configuration file on the VPS.
- [ ] Select a free loopback port and create the systemd service.
- [ ] Add the Caddy route without affecting other hosted sites.
- [ ] Replace the form's mailto submission with JavaScript submission.
- [ ] Test successful delivery and Reply-To.
- [ ] Test validation, honeypot, rate limiting and sending failures.
- [ ] Confirm errors preserve form contents and no secrets are exposed.
- [ ] Record final installation, restart and troubleshooting commands here.

No handler, service, Caddy route or form changes have been implemented as part of writing this document.
