# Contributing to ClaudGPT

Contributions are welcome. The goal is to improve reliability, maintainability, security, and user experience while keeping the project accessible to other developers.

## Before you start

1. Read the README and inspect the relevant code path before changing behavior.
2. Open an issue or discussion for large changes so the maintainers can agree on scope.
3. Keep pull requests focused and explain the problem they solve.
4. Preserve the original author and repository attribution in source and documentation.
5. Do not add API keys, Telegram tokens, database files, private user data, or real `.env` files.

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Add test credentials only to your local `.env`. Never commit that file.

## Checks before submitting

```bash
python -m py_compile main.py
```

For behavior changes, describe the manual test performed and the expected result. The project does not currently include a comprehensive automated test suite, so do not claim full test coverage based only on a syntax check.

## Pull request expectations

- Explain the change and any user-visible impact.
- Include steps to reproduce and verify fixes.
- Document new environment variables in both `.env.example` and README.md.
- Keep default limits conservative and explain any concurrency changes.
- Preserve secret redaction and input/file validation.
- Call out any change that can delete user data or modify retention behavior.
- Update documentation and architecture diagrams when the design changes.

## Security reports

Do not publish credentials or exploitable vulnerabilities in a public issue. Follow [SECURITY.md](SECURITY.md).
