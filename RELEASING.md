# Releasing LAN Paste

LAN Paste uses Semantic Versioning (MAJOR.MINOR.PATCH). Git tags are the source of truth for container versions.

- v0.1.0: first public MVP release.
- Patch (v0.1.1): backward-compatible fixes.
- Minor (v0.2.0): backward-compatible features.
- Major (v1.0.0): stable API and compatibility expectations.

## Release checklist

1. Merge release-ready changes into main only after CI passes.
2. Review the README, tests, security notes, and API or configuration changes.
3. In GitHub, open Releases → Draft a new release.
4. Create a new tag using the vMAJOR.MINOR.PATCH format, targeting main. Never reuse or move an existing release tag.
5. Write release notes covering user-visible changes, fixes, breaking changes, and upgrade steps. Publish the release.
6. The tag push triggers .github/workflows/publish.yml, which builds the Docker image and pushes these tags to GHCR:
   - ghcr.io/tomi3-11/lan-paste:MAJOR.MINOR.PATCH
   - ghcr.io/tomi3-11/lan-paste:MAJOR.MINOR
   - ghcr.io/tomi3-11/lan-paste:latest
7. Check the GitHub Actions run and verify the package tags on the repository's Packages page before announcing the release.

For example, releasing v0.1.0 publishes 0.1.0, 0.1, and latest. The latest tag tracks the most recently published version, so pin a full version tag for reproducible deployments.

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

This example binds only to localhost. To use LAN or Tailscale clients, adjust the host binding intentionally and configure firewall rules as described in the README. Replace 0.1.0 with the version you want to run. Back up the data volume before upgrades; do not remove it unless you intend to delete stored pastes.
