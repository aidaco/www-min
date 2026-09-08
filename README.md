# www-min

The current application behind https://aidan.software: a Python 3.14/FastAPI
website with contact submissions and administration stored in SQLite. The older
`aidaco/www` repository is not the deployed application.

## Development and tests

```sh
uv sync --locked --extra test
uv run --locked --extra test pytest
uv run wwwmin serve
```

Configuration is loaded from `~/.config/wwwmin/config.toml`; persistent data is
under `~/.local/share/wwwmin`. The test suite uses isolated in-memory databases
and never targets production. Do not commit database files, PEM keys, or config
containing secrets.

## Docker

```sh
docker build -t wwwmin:local .
docker run --rm --name wwwmin-test --read-only --cap-drop ALL \
  --security-opt no-new-privileges \
  --tmpfs /data:uid=10001,gid=10001,mode=0700 \
  -v "$PWD/docker/test-config.toml:/config/wwwmin/config.toml:ro" \
  -p 127.0.0.1:8000:8000 wwwmin:local
```

The example is disposable and uses a test-only JWT secret. Production mounts a
private configuration file and persistent data instead. The image requires
explicit configuration and disables the old in-process upgrade webhook.

`/api/health` checks the database and templates regardless of operating hours.
A healthy app returns HTTP 200 with `{"status":"ok","site_open":true}` (or
`false` when closed). Actual readiness failures return 503. The homepage retains
the website’s intentional closed-hours behavior. Production probes must not submit contact forms or modify accounts.

## Deployment

CI/CD verifies feature-branch PRs before main releases publish a tested
GHCR image and deploy it to Gooch. Jumper remains the public reverse proxy. See
[the deployment guide](docs/deployment/docker.md) for credentials, persistent
state, read-only production smoke tests, and code-only rollback.
