# Releasing LAN Paste

LAN Paste uses Semantic Versioning (MAJOR.MINOR.PATCH). Git tags are the source of truth for container versions.

- `v0.1.0`: first public MVP release.
- Patch (`v0.1.1`): backward-compatible fixes.
- Minor (`v0.2.0`): backward-compatible features.
- Major (`v1.0.0`): stable API and compatibility expectations.

## CI and release automation

The CI workflow runs tests and builds the Docker image for pull requests and pushes according to `.github/workflows/ci.yml`. A release tag triggers `.github/workflows/publish.yml`, which:

1. Rejects tags that are not stable `vMAJOR.MINOR.PATCH` versions (for example, `v0.1.0`).
2. Builds and publishes the container to GitHub Container Registry (GHCR).
3. Publishes version tags: `MAJOR.MINOR.PATCH`, `MAJOR.MINOR`, and `latest`.
4. After the image publish succeeds, creates a GitHub Release with automatically generated release notes.

You do not need to draft or publish a GitHub Release manually. Push a new version tag only after the intended commit is merged into `main`; the workflow handles the image and release. Never reuse or move an existing release tag.

For example, pushing `v0.1.0` publishes:

- `ghcr.io/tomi3-11/lan-paste:0.1.0`
- `ghcr.io/tomi3-11/lan-paste:0.1`
- `ghcr.io/tomi3-11/lan-paste:latest`

The `latest` tag tracks the most recently published stable version. Pin a full version tag for reproducible deployments.

## Release checklist

1. Ensure the CI checks pass and the release-ready changes are merged into `main`.
2. Review the README, tests, security notes, and API or configuration changes.
3. Create and push a new stable semantic-version tag, for example `v0.1.0`, targeting the intended commit on `main`.
4. Monitor the GitHub Actions run. The GitHub Release is created only if the container build and GHCR publish succeed.
5. Verify the release notes and image tags on the repository's Releases and Packages pages.

## First publication and package visibility

The first GHCR publication may create the package with private visibility. After the first successful publish, open the package page under the GitHub account or organization, review its access settings, and set it to Public if anyone should be able to pull it without authenticating. Confirm anonymous pulls work before announcing the release.

## Run a released image

Generate a strong admin token locally and store it securely. Do not commit a real token to the repository.

```sh
export PASTE_ADMIN_TOKEN="$(openssl rand -hex 32)"
docker volume create lan-paste-data

docker run -d \
  --name lan-paste \
  --restart unless-stopped \
  -p 127.0.0.1:8000:8000 \
  -e PASTE_ADMIN_TOKEN="$PASTE_ADMIN_TOKEN" \
  -e DEFAULT_TTL_HOURS=24 \
  -e DATA_DIR=/data \
  -v lan-paste-data:/data \
  ghcr.io/tomi3-11/lan-paste:0.1.0
```

This example binds only to localhost. To use LAN or Tailscale clients, adjust the host binding intentionally and configure firewall rules as described in the README. Replace `0.1.0` with the version you want to run. Back up the data volume before upgrades; do not remove it unless you intend to delete stored pastes.
