---
name: release-version
description: Release a new version of the bracket app by creating and pushing a git tag. Triggers the docker-publish GitHub Actions workflow which builds and pushes Docker images to GHCR. Use when the user says "release", "new version", "tag a version", "publish", or "deploy a new version".
---

# Release Version

Creates a semver git tag and pushes it to trigger the `docker-publish.yml` GitHub Actions workflow,
which builds and pushes two Docker images (frontend, backend) to `ghcr.io` in parallel matrix jobs.

## Workflow

### Step 1: Show current state

Run these commands to gather context:

```bash
git tag --sort=-v:refname | head -10
git log --oneline $(git describe --tags --abbrev=0)..HEAD | head -20
git status --short
```

Present to the user:
- Current latest tag
- Commits since last tag (what's being released)
- Any uncommitted changes (warn if present)

### Step 2: Ask for version

Ask the user to pick or type a version (multiple-choice question if your tool supports it).
Suggest the next logical versions based on the current tag (patch, minor, major). Version must
match `v*` pattern (e.g. `v3.0.0`).

Validate:
- Must start with `v` followed by semver (e.g. `v1.2.3`, `v2.0.0-rc1`)
- Must not already exist as a tag
- Warn if skipping versions (e.g. jumping from v2.2.5 to v4.0.0)

### Step 3: Confirm and tag

Before tagging, show a summary:

```
Release Summary:
  Version:  v3.0.0
  Branch:   dev
  Commits:  <count> commits since <previous tag>
  Remote:   origin (github.com/Kounex/bracket)
  Action:   docker-publish.yml will build and push to ghcr.io/kounex/bracket
```

Ask the user to confirm before proceeding.

### Step 4: Create and push

```bash
git tag -a <version> -m "Release <version>"
git push origin <version>
```

### Step 5: Verify

After pushing, show:
- The GitHub Actions URL: `https://github.com/Kounex/bracket/actions`
- The expected GHCR images that will be published:
  - `ghcr.io/kounex/bracket-frontend:<version>`
  - `ghcr.io/kounex/bracket-backend:<version>`

## Important Notes

- Only push tags to `origin` (your fork), never to `upstream`
- The `docker-publish.yml` workflow triggers on any `v*` tag push
- Images are built for `linux/amd64` only (QEMU arm64 frontend builds hang; all targets are x86_64)
- GHCR auth uses the repo's `GITHUB_TOKEN` — no extra secrets needed
- If the workflow fails, check Actions tab; the tag can be deleted and recreated:
  ```bash
  git tag -d <version>
  git push origin --delete <version>
  ```
