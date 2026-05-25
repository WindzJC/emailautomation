# Mac Secrets Checklist

The handoff archive intentionally excludes local secrets and credentials. Recreate or copy these manually on the Mac using a private channel.

## Required Runtime Secrets

- SendGrid API key and any SendGrid webhook/auth tokens.
- Gmail/private JC sender credentials, OAuth files, app passwords, or local account tokens.
- `.env` and `.env.local` values, including dashboard auth/session secrets and provider credentials.
- Any files under `KEYS/` or equivalent local credential directories.
- Any OAuth/token/session files used by Gmail, private sender auth, webhook auth, or browser/session login.

## Setup Notes

- Do not commit these secrets.
- Do not paste secret values into tickets, PRs, chat, screenshots, or logs.
- After extraction on Mac, recreate `.env` from the current machine manually and verify dashboard auth plus SendGrid/private sender preflight before any send.
