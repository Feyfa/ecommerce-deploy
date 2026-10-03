#!/usr/bin/env python3
"""Reclaim only unreferenced Ecommerce application digests on the local VM.

Run from the deploy checkout. Manifest files are parsed, never sourced. Mutating
modes require the deployment's inherited flock descriptor, held across pull,
activation and cleanup. No containers, volumes, caches or registry data change.
"""

import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys


REPOSITORIES = {
    "FRONTEND_IMAGE": "ghcr.io/feyfa/ecommerce-frontend",
    "BACKEND_IMAGE": "ghcr.io/feyfa/ecommerce-backend-php",
    "BACKEND_NGINX_IMAGE": "ghcr.io/feyfa/ecommerce-backend-nginx",
}
MIN_FREE_BYTES = 3 * 1024 ** 3
MIN_FREE_INODES = 10000
IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}")


class RetentionError(Exception):
    """Signal incomplete safety evidence or insufficient deployment capacity."""


def docker(*arguments: str) -> str:
    """Execute a bounded Docker command; propagate failures without guessing state."""
    result = subprocess.run(
        ["docker", *arguments], capture_output=True, text=True, timeout=60,
    )
    if result.returncode:
        raise RetentionError(f"Docker {arguments[0]} failed: {result.stderr.strip()}")
    return result.stdout


def docker_json(*arguments: str):
    """Decode Docker JSON and reject malformed inspection responses."""
    return json.loads(docker(*arguments))


def read_manifest(path: Path) -> set[str]:
    """Require three unique immutable application references in an existing file."""
    values = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator:
            raise RetentionError(f"Invalid manifest assignment: {path}")
        if key not in REPOSITORIES:
            continue
        if key in values or not re.fullmatch(
            re.escape(REPOSITORIES[key]) + r"@sha256:[0-9a-f]{64}", value,
        ):
            raise RetentionError(f"Invalid or duplicate {key}: {path}")
        values[key] = value
    if set(values) != set(REPOSITORIES):
        raise RetentionError(f"Incomplete image manifest: {path}")
    return set(values.values())


def protected_references(environment: str, candidate: set[str]) -> tuple[set[str], bool]:
    """Protect both environments' recorded releases; disable deletion at first cutover."""
    references = set(candidate)
    current = Path(f"env/{environment}/images.env")
    for name in ("staging", "production"):
        active = Path(f"env/{name}/images.env")
        previous = Path(f"env/{name}/images.previous.env")
        if previous.exists() and not active.exists():
            raise RetentionError(f"Previous manifest without active manifest: {previous}")
        for path in (active, previous):
            if path.exists():
                references.update(read_manifest(path))
    return references, current.exists()


def inventory() -> list[dict]:
    """Inspect full image IDs, including aliases, instead of relying on list sizes."""
    ids = sorted(set(docker("image", "ls", "--quiet", "--no-trunc").split()))
    images = []
    for offset in range(0, len(ids), 50):
        images.extend(docker_json("image", "inspect", *ids[offset:offset + 50]))
    for image in images:
        if not IMAGE_ID.fullmatch(image["Id"]):
            raise RetentionError("Unrecognized image ID")
    return images


def eligible(environment: str, candidate: set[str]) -> list[dict]:
    """Find oldest digest-only project images outside every manifest/container reference.

    Resolve saved digests independently through Docker: a second digest or tag
    can name the same image ID. Unknown aliases and mutable tags are retained.
    Missing saved images or failed container inspection stop the entire cleanup.
    """
    saved, enabled = protected_references(environment, set())
    references = saved | candidate
    protected_ids = set()
    for reference in sorted(saved):
        inspected = docker_json("image", "inspect", reference)
        if not IMAGE_ID.fullmatch(inspected[0]["Id"]):
            raise RetentionError("Unrecognized saved image ID")
        protected_ids.add(inspected[0]["Id"])
    container_ids = docker("ps", "--all", "--quiet", "--no-trunc").split()
    for offset in range(0, len(container_ids), 50):
        for container in docker_json("container", "inspect", *container_ids[offset:offset + 50]):
            protected_ids.add(container["Image"])
    images = inventory()
    for image in images:
        if references.intersection(image.get("RepoDigests") or []):
            protected_ids.add(image["Id"])
    if not enabled:
        print("First image release: automatic deletion disabled")
        return []
    result = []
    for image in images:
        digests = image.get("RepoDigests") or []
        if image["Id"] in protected_ids:
            continue
        # Docker 29 can repeat immutable digests in RepoTags. Only those exact
        # aliases are allowed; ordinary tags and unknown ownership stay intact.
        if set(image.get("RepoTags") or []) - set(digests) or not digests or any(
            not any(re.fullmatch(re.escape(repo) + r"@sha256:[0-9a-f]{64}", ref)
                    for repo in REPOSITORIES.values()) for ref in digests
        ):
            continue
        result.append(image)
    return sorted(result, key=lambda image: (image["Created"], image["Id"]))


def storage_paths() -> list[Path]:
    """Check daemon storage and manifest filesystems, including Docker 29 containerd.

    The supported VM layout uses local Docker and /var/lib/containerd. Refuse
    remote daemons and unknown containerd layouts rather than check a wrong disk.
    """
    host = os.environ.get("DOCKER_HOST", "")
    context = docker("context", "inspect")
    endpoint = json.loads(context)[0]["Endpoints"]["docker"]["Host"]
    if (host and not host.startswith("unix://")) or not endpoint.startswith("unix://"):
        raise RetentionError("Retention requires a local Docker daemon")
    info = docker_json("info", "--format", "{{json .}}")
    paths = [Path(info["DockerRootDir"]), Path("env").resolve()]
    status = json.dumps(info.get("DriverStatus", []))
    if "containerd" in status:
        containerd = Path("/var/lib/containerd")
        if not containerd.is_dir():
            raise RetentionError("Unsupported containerd storage layout")
        config = Path("/etc/containerd/config.toml")
        if config.exists():
            # A custom root needs explicit support, not an inferred capacity check.
            for line in config.read_text().splitlines():
                if re.match(r"^root\s*=", line.strip()) and not re.fullmatch(
                    r'''root\s*=\s*["']/var/lib/containerd["']\s*(?:#.*)?''', line.strip(),
                ):
                    raise RetentionError("Custom containerd root requires operator review")
        paths.append(containerd)
    return paths


def capacity(paths: list[Path]) -> bool:
    """Measure actual available blocks and inodes once per distinct filesystem."""
    enough = True
    seen = set()
    for path in paths:
        device = path.stat().st_dev
        if device in seen:
            continue
        seen.add(device)
        stats = os.statvfs(path)
        available = stats.f_bavail * stats.f_frsize
        print(f"Space {path}: {available} bytes, {stats.f_favail} inodes; "
              f"required {MIN_FREE_BYTES} bytes, {MIN_FREE_INODES} inodes")
        enough = enough and available >= MIN_FREE_BYTES and stats.f_favail >= MIN_FREE_INODES
    return enough


def retain(environment: str, mode: str, candidate: set[str]) -> None:
    """Revalidate each deletion and measure reclaimed capacity, without forced removal."""
    # --- step 1 - start - validate protection and capacity before any deletion
    paths = storage_paths()
    images = eligible(environment, candidate)
    references, _ = protected_references(environment, candidate)
    print(f"Retention {mode}: {len(images)} eligible historical images; "
          "all container images and uncertain aliases protected")
    for reference in sorted(references):
        print(f"Protected reference {reference}")
    sufficient = capacity(paths)
    if mode == "ensure-space" and sufficient:
        return
    # --- step 1 - end - validate protection and capacity before any deletion

    # --- step 2 - start - remove only candidates still proven safe
    for image in images:
        if mode == "dry-run":
            print(f"Would remove {image['Id']}: {', '.join(image['RepoDigests'])}")
            continue
        fresh = {item["Id"]: item for item in eligible(environment, candidate)}
        current = fresh.get(image["Id"])
        if current is None or set(current["RepoDigests"]) != set(image["RepoDigests"]):
            print(f"Skipped changed/protected image {image['Id']}")
            continue
        for reference in current["RepoDigests"]:
            print(f"Removing historical digest {reference}")
            docker("image", "rm", reference)
        sufficient = capacity(paths)
        if mode == "ensure-space" and sufficient:
            return
    # --- step 2 - end - remove only candidates still proven safe

    if mode == "ensure-space" and not capacity(paths):
        raise RetentionError("Insufficient capacity after safe cleanup; deployment not started")


def main() -> int:
    """Validate CLI inputs and require the inherited deployment lock for mutation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("environment", choices=("staging", "production"))
    parser.add_argument("mode", choices=("dry-run", "ensure-space", "cleanup"))
    parser.add_argument("--candidate", nargs=3, default=[])
    parser.add_argument("--lock-fd", type=int)
    args = parser.parse_args()
    try:
        for reference, repo in zip(args.candidate, REPOSITORIES.values()):
            if not re.fullmatch(re.escape(repo) + r"@sha256:[0-9a-f]{64}", reference):
                raise RetentionError("Invalid candidate reference")
        if args.mode != "dry-run":
            if args.lock_fd is None:
                raise RetentionError("Mutating retention requires the deployment lock")
            expected = os.stat("tmp/image-release.lock")
            actual = os.fstat(args.lock_fd)
            if (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino):
                raise RetentionError("Unexpected deployment lock descriptor")
            fcntl.flock(args.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        retain(args.environment, args.mode, set(args.candidate))
    except (RetentionError, OSError, ValueError, KeyError, IndexError, TypeError,
            subprocess.TimeoutExpired) as error:
        print(f"Image retention stopped: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
