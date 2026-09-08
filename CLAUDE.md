# Repository guidance

This is the current `aidan.software` application. Use Python 3.14 and `uv.lock`;
install with `uv sync --locked --extra test`, test with `uv run pytest`.
Keep the existing pinned appbase Git dependency unless deliberately updating it.

Use feature branches and pull requests. Read [deployment documentation](docs/deployment/docker.md)
for the Piac/application ownership split, CI/CD, and rollback limitations.
Production checks must use only `scripts/smoke.py`; full tests use disposable state.
Do not submit production contact forms or send test email. Never commit SQLite
files, push private keys, configuration secrets, or environment files.

Keep README and the deployment guide current when changing delivery or operations.
The health endpoint reports application readiness separately from opening hours.
