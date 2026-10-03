"""Verify retention safety using isolated manifests and simulated Docker state."""

import contextlib
import fcntl
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "retention", Path(__file__).resolve().parents[1] / "scripts/manage-image-retention.py",
)
retention = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retention)


def image(number: int, repository: str = "ghcr.io/feyfa/ecommerce-backend-php") -> dict:
    """Build distinct immutable image identities with ordered creation timestamps."""
    digest = f"sha256:{number:064x}"
    return {"Id": digest, "RepoDigests": [f"{repository}@{digest}"],
            "RepoTags": [], "Created": f"2026-10-{number:02d}T00:00:00Z"}


class RetentionTests(unittest.TestCase):
    """Exercise manifests, protection, deletion sequencing and filesystem checks."""

    def setUp(self) -> None:
        """Create a disposable checkout and substitute the Docker command boundary."""
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        previous = Path.cwd()
        os.chdir(self.directory.name)
        self.addCleanup(os.chdir, previous)
        Path("env/staging").mkdir(parents=True)
        self.images = [image(n) for n in range(1, 6)]
        self.saved = {}
        self.containers = []
        self.removed = []
        self.write_manifest("env/staging/images.env", 4)
        self.write_manifest("env/staging/images.previous.env", 3)
        self.addCleanup(patch.stopall)
        patch.object(retention, "docker", side_effect=self.docker).start()
        patch.object(retention, "storage_paths", return_value=[Path("env")]).start()
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def write_manifest(self, path: str, number: int) -> None:
        """Record a complete release whose three digests alias one protected ID."""
        lines = []
        for key, repo in retention.REPOSITORIES.items():
            ref = f"{repo}@sha256:{number:064x}"
            lines.append(f"{key}={ref}")
            self.saved[ref] = image(number)
        Path(path).write_text("\n".join(lines) + "\n")

    def docker(self, *args: str) -> str:
        """Expose realistic inspection responses and record explicit digest removals."""
        if args[:2] == ("image", "ls"):
            return "\n".join(item["Id"] for item in self.images)
        if args[:2] == ("image", "inspect"):
            result = []
            for ref in args[2:]:
                if ref in self.saved:
                    result.append(self.saved[ref])
                else:
                    result.append(next(item for item in self.images if item["Id"] == ref))
            return json.dumps(result)
        if args[0] == "ps":
            return "\n".join(str(n) for n in range(len(self.containers)))
        if args[:2] == ("container", "inspect"):
            return json.dumps([{"Image": self.containers[int(n)]} for n in args[2:]])
        if args[:2] == ("image", "rm"):
            self.removed.append(args[2])
            self.images = [item for item in self.images if args[2] not in item["RepoDigests"]]
            return "Deleted"
        raise AssertionError(f"Unexpected Docker mutation/command: {args}")

    def test_protect_saved_candidate_and_stopped_container(self) -> None:
        """Retain releases and containers by ID, including a candidate digest."""
        self.containers = [image(2)["Id"]]
        self.assertEqual([item["Id"] for item in retention.eligible(
            "staging", set(image(5)["RepoDigests"]),
        )], [image(1)["Id"]])

    def test_alias_digest_of_saved_image_is_protected(self) -> None:
        """A different listed digest cannot make a saved image ID eligible."""
        self.images[3]["RepoDigests"] = image(9)["RepoDigests"]
        self.assertNotIn(image(4)["Id"], [item["Id"] for item in retention.eligible("staging", set())])

    def test_foreign_and_tagged_images_are_skipped(self) -> None:
        """Avoid deleting images with foreign aliases, tags or unknown ownership."""
        self.images[0]["RepoDigests"].append("other/application@sha256:" + "a" * 64)
        self.images[1]["RepoTags"] = ["ghcr.io/feyfa/ecommerce-backend-php:keep"]
        self.images[4]["RepoDigests"] = []
        self.assertEqual(retention.eligible("staging", set()), [])

    def test_docker29_digest_tags_remain_eligible(self) -> None:
        """Accept the immutable digest alias Docker 29 repeats in RepoTags."""
        self.images[0]["RepoTags"] = self.images[0]["RepoDigests"][:]
        self.assertIn(image(1)["Id"], [item["Id"] for item in retention.eligible("staging", set())])

    def test_both_environments_protect_releases(self) -> None:
        """Retain a second environment's manifest on the same daemon."""
        Path("env/production").mkdir()
        self.write_manifest("env/production/images.env", 1)
        self.assertNotIn(image(1)["Id"], [item["Id"] for item in retention.eligible("staging", set())])

    def test_first_release_never_deletes(self) -> None:
        """Keep pre-cutover images when no active or previous manifest exists."""
        Path("env/staging/images.env").unlink()
        Path("env/staging/images.previous.env").unlink()
        self.assertEqual(retention.eligible("staging", set()), [])

    def test_orphan_previous_manifest_is_rejected(self) -> None:
        """Refuse ambiguous release state rather than discard rollback images."""
        Path("env/staging/images.env").unlink()
        with self.assertRaises(retention.RetentionError):
            retention.eligible("staging", set())

    def test_malformed_duplicate_and_missing_manifest_keys(self) -> None:
        """Invalid manifests cannot authorize any image removal."""
        path = Path("env/staging/images.env")
        valid = path.read_text()
        for content in ("bad line", valid + valid, valid.replace("sha256:", "tag:"), ""):
            with self.subTest(content=content):
                path.write_text(content)
                with self.assertRaises(retention.RetentionError):
                    retention.eligible("staging", set())
        self.assertEqual(self.removed, [])

    def test_inspection_failure_stops_cleanup(self) -> None:
        """Never convert unavailable safety evidence into an empty protection set."""
        with patch.object(retention, "docker", side_effect=retention.RetentionError("inspect failed")):
            with self.assertRaises(retention.RetentionError):
                retention.retain("staging", "cleanup", set())
        self.assertEqual(self.removed, [])

    def test_sufficient_space_does_not_remove_before_pull(self) -> None:
        """Preserve historical images at preflight when capacity already passes."""
        with patch.object(retention, "capacity", return_value=True):
            retention.retain("staging", "ensure-space", set())
        self.assertEqual(self.removed, [])

    def test_low_space_reclaims_oldest_until_sufficient(self) -> None:
        """Stop reclaiming as soon as a real filesystem measurement passes."""
        with patch.object(retention, "capacity", side_effect=[False, True]):
            retention.retain("staging", "ensure-space", set())
        self.assertEqual(self.removed, image(1)["RepoDigests"])

    def test_insufficient_after_cleanup_fails(self) -> None:
        """Signal a capacity failure after all safe options have been exhausted."""
        with patch.object(retention, "capacity", return_value=False):
            with self.assertRaisesRegex(retention.RetentionError, "Insufficient capacity"):
                retention.retain("staging", "ensure-space", set())
        self.assertEqual(len(self.removed), 3)

    def test_dry_run_has_no_removal(self) -> None:
        """Describe eligibility without deleting images even under disk pressure."""
        with patch.object(retention, "capacity", return_value=False):
            retention.retain("staging", "dry-run", set())
        self.assertEqual(self.removed, [])

    def test_cleanup_removes_all_unprotected_historical_images(self) -> None:
        """Successful-release cleanup enforces retention even with ample space."""
        with patch.object(retention, "capacity", return_value=True):
            retention.retain("staging", "cleanup", set())
        self.assertEqual(self.removed, [image(n)["RepoDigests"][0] for n in (1, 2, 5)])

    def test_protection_changes_before_deletion(self) -> None:
        """Recheck safety immediately before removal instead of trusting a stale list."""
        with patch.object(retention, "eligible", side_effect=[[image(1)], []]), \
                patch.object(retention, "capacity", return_value=True):
            retention.retain("staging", "cleanup", set())
        self.assertEqual(self.removed, [])

    def test_removal_failure_is_propagated(self) -> None:
        """A Docker deletion error is not silently presented as reclaimed space."""
        with patch.object(retention, "eligible", return_value=[image(1)]), \
                patch.object(retention, "docker", side_effect=retention.RetentionError("remove denied")), \
                patch.object(retention, "capacity", return_value=True):
            with self.assertRaisesRegex(retention.RetentionError, "remove denied"):
                retention.retain("staging", "cleanup", set())

    def test_capacity_checks_bytes_and_inodes(self) -> None:
        """Require both available capacity measures rather than total disk size."""
        stats = os.statvfs("env")
        values = list(stats)
        values[4] = 0
        with patch.object(retention.os, "statvfs", return_value=os.statvfs_result(values)):
            self.assertFalse(retention.capacity([Path("env")]))
        values[4] = retention.MIN_FREE_BYTES // stats.f_frsize + 1
        values[7] = 0
        with patch.object(retention.os, "statvfs", return_value=os.statvfs_result(values)):
            self.assertFalse(retention.capacity([Path("env")]))

    def test_mutation_requires_lock(self) -> None:
        """The CLI refuses a mutating command without the inherited lock FD."""
        with patch.object(retention.sys, "argv", ["retention", "staging", "cleanup"]), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(retention.main(), 1)
        self.assertEqual(self.removed, [])

    def test_real_lock_contention_rejects_mutation(self) -> None:
        """A separately opened locked inode blocks the helper before Docker removal."""
        Path("tmp").mkdir()
        with Path("tmp/image-release.lock").open("a") as owner, \
                Path("tmp/image-release.lock").open("a") as contender:
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with patch.object(retention.sys, "argv", ["retention", "staging", "cleanup",
                                                     "--lock-fd", str(contender.fileno())]), \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(retention.main(), 1)
        self.assertEqual(self.removed, [])

    def test_wrong_lock_descriptor_is_rejected(self) -> None:
        """An unrelated descriptor cannot authorize cleanup through the CLI."""
        Path("tmp").mkdir()
        Path("tmp/image-release.lock").touch()
        with Path("other-lock").open("a") as handle, \
                patch.object(retention.sys, "argv", ["retention", "staging", "cleanup",
                                                     "--lock-fd", str(handle.fileno())]), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(retention.main(), 1)
        self.assertEqual(self.removed, [])

    def test_saved_candidate_still_requires_saved_inspection(self) -> None:
        """A candidate equal to active release does not bypass missing saved-image checks."""
        refs = retention.read_manifest(Path("env/staging/images.env"))
        with patch.object(retention, "docker_json", side_effect=retention.RetentionError("missing saved image")):
            with self.assertRaises(retention.RetentionError):
                retention.eligible("staging", refs)

    def test_storage_paths_containerd_and_remote_daemon(self) -> None:
        """Check Docker 29's containerd store and refuse an unrelated remote daemon."""
        patch.stopall()
        replies = [json.dumps([{"Endpoints": {"docker": {"Host": "unix:///var/run/docker.sock"}}}]),
                   json.dumps({"DockerRootDir": "/var/lib/docker",
                               "DriverStatus": [["driver-type", "io.containerd.snapshotter.v1"]]})]
        with patch.dict(retention.os.environ, {"DOCKER_HOST": ""}), \
                patch.object(retention, "docker", side_effect=replies), \
                patch.object(retention.Path, "is_dir", return_value=True), \
                patch.object(retention.Path, "exists", return_value=False):
            self.assertIn(Path("/var/lib/containerd"), retention.storage_paths())
        with patch.dict(retention.os.environ, {"DOCKER_HOST": "tcp://remote:2375"}), \
                patch.object(retention, "docker", return_value=replies[0]):
            with self.assertRaises(retention.RetentionError):
                retention.storage_paths()

    def test_custom_containerd_root_is_rejected(self) -> None:
        """Refuse a custom store instead of accepting free space on the wrong filesystem."""
        patch.stopall()
        with patch.dict(retention.os.environ, {"DOCKER_HOST": ""}), \
                patch.object(retention, "docker", side_effect=[
                    json.dumps([{"Endpoints": {"docker": {"Host": "unix:///var/run/docker.sock"}}}]),
                    json.dumps({"DockerRootDir": "/var/lib/docker", "DriverStatus": ["containerd"]}),
                ]), patch.object(retention.Path, "is_dir", return_value=True), \
                patch.object(retention.Path, "exists", return_value=True), \
                patch.object(retention.Path, "read_text", return_value='root = "/other/storage"'):
            with self.assertRaisesRegex(retention.RetentionError, "Custom containerd"):
                retention.storage_paths()


if __name__ == "__main__":
    unittest.main()
