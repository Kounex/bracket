#!/usr/bin/env python3
"""Refresh pinned base images in Dockerfiles, without Dependabot.

For repos where Dependabot can't run (forks have version updates off, and
turning them on would also wake the upstream's own Dependabot config).
Used by base-refresh.example.yml. Canonical copy:
it-env/templates/container-image/release-flows/refresh_bases.py

Every `FROM <image>:<tag>@sha256:<digest>` line is checked:
- newer patch in the same line (same numbers except the last, same suffix):
  `3.14.5-alpine3.22` -> `3.14.6-alpine3.22`; `2.11.7-alpine` -> `2.11.8-alpine`
- otherwise, a new digest for the same tag (upstream rebuilt it)
Minor/major moves are never made; they stay a human decision.

usage: refresh_bases.py <Dockerfile>...   (rewrites in place, prints changes)
Exit code 0 always; prints nothing when everything is current.
"""
import json
import re
import sys
import urllib.request

FROM = re.compile(r"^(FROM\s+)([^\s:@]+(?:/[^\s:@]+)*):([^\s@]+)@(sha256:[0-9a-f]{64})(.*)$")
ACCEPT = ", ".join([
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
])


def split(image):
    first, _, rest = image.partition("/")
    if rest and ("." in first or ":" in first):
        return first, rest
    return "registry-1.docker.io", image if "/" in image else "library/" + image


def token(reg, repo):
    url = {
        "registry-1.docker.io": f"https://auth.docker.io/token?service=registry.docker.io&scope=repository:{repo}:pull",
        "ghcr.io": f"https://ghcr.io/token?scope=repository:{repo}:pull",
    }.get(reg)
    return json.load(urllib.request.urlopen(url, timeout=30)).get("token") if url else None


def digest(reg, repo, tag, tok):
    req = urllib.request.Request(
        f"https://{reg}/v2/{repo}/manifests/{tag}", method="HEAD",
        headers={"Accept": ACCEPT, **({"Authorization": f"Bearer {tok}"} if tok else {})})
    return urllib.request.urlopen(req, timeout=30).headers["Docker-Content-Digest"]


def tags(reg, repo, tok, name_prefix):
    if reg == "registry-1.docker.io":
        out, url = [], (f"https://hub.docker.com/v2/repositories/{repo}/tags"
                        f"?page_size=100&name={name_prefix}")
        while url and len(out) < 1000:
            d = json.load(urllib.request.urlopen(url, timeout=30))
            out += [t["name"] for t in d["results"]]
            url = d.get("next")
        return out
    req = urllib.request.Request(f"https://{reg}/v2/{repo}/tags/list?n=10000",
                                 headers={"Authorization": f"Bearer {tok}"} if tok else {})
    return json.load(urllib.request.urlopen(req, timeout=30)).get("tags") or []


def newest_patch(tag, candidates):
    """Newest tag of the same line: last number may grow, everything else fixed."""
    nums = re.match(r"(\d+(?:\.\d+)*)(.*)", tag)
    if not nums:
        return tag
    parts, suffix = nums.group(1).split("."), nums.group(2)
    head = ".".join(parts[:-1])
    pat = re.compile(re.escape(head + "." if head else "") + r"(\d+)" + re.escape(suffix))
    best = tag
    for c in candidates:
        cm = pat.fullmatch(c)
        if cm and int(cm.group(1)) > int(re.fullmatch(pat, best).group(1)):
            best = c
    return best


def refresh(path):
    lines = open(path).read().splitlines(keepends=True)
    changed = False
    for i, line in enumerate(lines):
        m = FROM.match(line.rstrip("\n"))
        if not m:
            continue
        pre, image, tag, old_digest, rest = m.groups()
        reg, repo = split(image)
        tok = token(reg, repo)
        prefix = re.match(r"\d+(?:\.\d+)*", tag)
        prefix = ".".join(prefix.group(0).split(".")[:-1]) + "." if prefix and "." in prefix.group(0) else ""
        new_tag = newest_patch(tag, tags(reg, repo, tok, prefix))
        new_digest = digest(reg, repo, new_tag, tok)
        if (new_tag, new_digest) != (tag, old_digest):
            lines[i] = f"{pre}{image}:{new_tag}@{new_digest}{rest}\n"
            print(f"{path}: {image}:{tag} -> {new_tag}" + ("" if new_tag != tag else " (new digest)"))
            changed = True
    if changed:
        open(path, "w").write("".join(lines))


if __name__ == "__main__":
    for p in sys.argv[1:]:
        refresh(p)
