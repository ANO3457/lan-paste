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
3. If Docker Hub credentials are configured, publishes the same image to Docker Hub.
4. Publishes version tags: `MAJOR.MINOR.PATCH`, `MAJOR.MINOR`, and `latest` to each enabled registry.
5. After the GHCR image publish succeeds, creates a GitHub Release with automatically generated release notes.

You do not need to draft or publish a GitHub Release manually. Push a new version tag only after the intended commit is merged into `main`; the workflow handles image publishing and the release. Never reuse or move an existing release tag.

## Docker Hub setup (optional)

To enable Docker Hub publishing, create a Docker Hub repository named `lan-paste` under your Docker Hub account. Then add these repository Actions secrets in GitHub under **Settings → Secrets and variables → Actions**:

- `DOCKERHUB_USERNAME`: your Docker Hub username.
- `DOCKERHUB_TOKEN`: a Docker Hub access token with permission to push to the repository.

Use an access token, not your Docker Hub password. Do not commit credentials or paste them into issues or pull requests.

If either secret is missing, the workflow skips Docker Hub publishing and continues publishing to GHCR. After configuring both secrets, the next new release tag will publish to both registries. The existing `v0.1.0` tag will not automatically rerun just because secrets were added; do not move or reuse a release tag. Verify a later release's workflow run and pull the published image from Docker Hub.

## Image tags

For example, pushing `v0.1.0` publishes these GHCR tags:

- `ghcr.io/tomi3-11/lan-paste:0.1.0`
- `ghcr.io/tomi3-11/lan-paste:0.1`
- `ghcr.io/tomi3-11/lan-paste:latest`

When Docker Hub is configured, the same tags are published as `docker.io/DOCKERHUB_USERNAME/lan-paste:0.1.0`, `:0.1`, and `:latest`, where `DOCKERHUB_USERNAME` is the account configured in the GitHub secret.

The `latest` tag tracks the most recently published stable version. Pin a full version tag for reproducible deployments.

## Release checklist

1. Ensure CI checks pass and the release-ready changes are merged into `main`.
2. Review the README, tests, security notes, and API or configuration changes.
3. Confirm Docker Hub secrets are configured if publishing to Docker Hub is intended.
4. Create and push a new stable semantic-version tag, for example `v0.1.1`, targeting the intended commit on `main`.
5. Monitor the GitHub Actions run. The GitHub Release is created only if the GHCR container build and publish succeed.
6. Verify release notes and image tags on the repository's Releases and Packages pages and, if enabled, Docker Hub.

## First GHCR publication and package visibility

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
