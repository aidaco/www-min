# Website deployment

`www-min` is the current application for https://aidan.software; the older
`aidaco/www` repository is retired. Piac previously ran commit `07aa614` as
`wwwmin.service` on Jumper. The container migration to Gooch is complete. Changes are committed locally on
`deploy/gooch-container`; publication to the existing public repository and
enrollment of its Actions deployment key await explicit approval. Production
currently uses a tested image transferred through the existing trusted host SSH
connection. See Piac's runbook for the bootstrap image and retained data copies.

## Ownership and traffic

Piac owns Gooch's Docker Compose configuration at `/opt/wwwmin/compose.yml`,
WireGuard, the restricted deployment account/helper, runtime secrets, backups,
monitoring, and Jumper's Caddy proxy. This repository owns application code,
its locked Python environment, Dockerfile, tests, and GitHub Actions releases.

Traffic follows browser → Jumper Caddy → WireGuard → Gooch `10.8.0.7:8000`.
Jumper continues serving `/dl/` and `/resume.pdf` directly and hosts SMTP.
The container runs as UID/GID 10001, with a read-only root filesystem, dropped
capabilities, bounded resources and logs, and writable SQLite state only at
`/data/wwwmin` (host `/var/lib/wwwmin`). Secrets are mounted read-only from
`/etc/wwwmin/config.toml`; none belong in an image or GitHub build arguments.

## Automated releases

Feature branches go through pull requests. `Verify` builds the locked production
image, runs the application suite on Python 3.14, and smoke-tests a disposable
container with email disabled. Main releases require an associated merged PR.
The tested image is published to private `ghcr.io/aidaco/www-min` and deployed by
exact digest, never by a mutable `latest` tag.

CD connects to Gooch as `wwwmin-deploy`, whose SSH key can only invoke the
root-owned `/usr/local/sbin/wwwmin-deploy` helper. It cannot open a shell, forward
ports, use general sudo, or deploy Arcade images. The private key is stored in
Piac's encrypted vault and the repository's `WWWMIN_DEPLOY_SSH_KEY` Actions
secret once enrolled. The host key is pinned in the workflow. A temporary
`GITHUB_TOKEN` travels over SSH stdin and is removed from the host after pulling;
there is no permanent registry token on Gooch.

The helper serializes releases, waits for container health, and atomically records
`release.env` and `previous.env`. Ansible preserves these files. After deployment,
`scripts/smoke.py https://aidan.software` checks health, homepage, login page, CSS,
and JavaScript using GET only. It never submits forms, authenticates, or changes
production state. There is no option to bypass these public checks in CI.
Failed startup or public smoke checks trigger code rollback; stale rollback
requests cannot overwrite newer releases. Deployment jobs do not cancel each other.

## Health and state

`/api/health` returns 200 with `{"status":"ok","site_open":false}` outside opening
hours. Actual database/template readiness failure returns 503 with a generic
error. The homepage retains its closed-hours page and 503 status; smoke tests
accept that specific page, not arbitrary server errors.

The SQLite database contains admin credentials, contact submissions, and push
subscriptions. Preserve both it and `vapid-private-key.pem`, plus the existing
vault JWT secret. SQLite's online backup API is required for live copies; copying
only the database while a WAL is active can lose committed records.

Rollback replaces code only: it does not undo database changes. Changes to schema
must remain compatible with the previous release or include an explicit migration
and recovery plan. Take a fresh database snapshot before such a release. Never
run the full test suite against production or reset its state during deployment.

## Operations

On Gooch, inspect `sudo docker ps` and `sudo docker logs --tail 100 wwwmin`.
Health is available inside the VPN at `http://10.8.0.7:8000/api/health`.
For public read-only validation, run `python3 scripts/smoke.py https://aidan.software`.
Routine application changes need a merged PR, not an Ansible run. Infrastructure
changes use Piac's `playbooks/wwwmin.yml`; its handler reapplies the CD-selected image.

See [Piac's website runbook](../../../piac/docs/hosts/gooch-wwwmin.md) for
migration, backup, and rollback procedures (sibling checkouts assumed).
