# Security Policy

## Supported version

Security fixes should target the latest version on the canonical upstream repository:
https://github.com/RadLamine/ClaudGPT

## Reporting a vulnerability

Please do not publish live credentials, private user data, or exploit details in a public issue. Use GitHub's private vulnerability reporting feature for the repository if it is enabled, or contact the maintainer through the GitHub profile:
https://github.com/RadLamine

Include the affected version/commit, impact, reproduction steps, and a suggested mitigation where possible. Redact all tokens and personal data from logs.

## Secrets and deployment

- Keep `.env` out of version control.
- Rotate any Telegram, Groq, or Cloudflare token that is exposed.
- Use least-privilege Cloudflare API tokens.
- Restrict `ADMIN_ID` to the intended administrator.
- Back up the SQLite database securely and protect the backup as user data.
- Review the cleanup and emergency-wipe behavior before deploying to real users.
