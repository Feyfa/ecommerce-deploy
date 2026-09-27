#!/usr/bin/env python3
"""Copy allowlisted Vite build values from a VM env file into GITHUB_ENV.

The VM remains the configuration source. The script masks browser keys in
GitHub Actions logs and ignores deployment-only variables such as HTTP ports.
All eight Vite
arguments must be present so a missing value cannot silently create a bundle
with Dockerfile defaults intended for a different environment.
"""

from pathlib import Path
import os
import re
import sys


BUILD_KEYS = (
    "VITE_APP_BACKEND_BASE_URL",
    "VITE_SYMLINK_FOLDER",
    "VITE_GEOAPIFY_API_KEY",
    "VITE_CLERK_PUBLISHABLE_KEY",
    "VITE_CLERK_SIGN_IN_URL",
    "VITE_CLERK_SIGN_UP_URL",
    "VITE_FEATURE_CLERK_PASSKEY",
    "VITE_FEATURE_CLERK_TOTP",
)


def main() -> int:
    """Validate a simple dotenv file and export only the frontend build keys."""
    if len(sys.argv) != 3:
        print("Usage: export-frontend-build-env.py FRONTEND_ENV GITHUB_ENV", file=sys.stderr)
        return 2

    source = Path(sys.argv[1])
    output = Path(sys.argv[2])
    values: dict[str, str] = {}

    # --- step 1 - start - read the VM file without executing its contents
    for line_number, raw_line in enumerate(source.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            print(f"Invalid env assignment on line {line_number}", file=sys.stderr)
            return 1

        if key not in BUILD_KEYS:
            continue

        if key in values:
            print(f"Duplicate {key} on line {line_number}", file=sys.stderr)
            return 1

        value = value.strip()
        if value.startswith(("'", '"')):
            if len(value) < 2 or value[-1] != value[0]:
                print(f"Unclosed quote for {key} on line {line_number}", file=sys.stderr)
                return 1
            value = value[1:-1]

        if not value or "\r" in value or "\n" in value:
            print(f"Empty or multiline value for {key}", file=sys.stderr)
            return 1

        values[key] = value
    # --- step 1 - end - read the VM file without executing its contents

    missing = [key for key in BUILD_KEYS if key not in values]
    if missing:
        print(f"Missing frontend build keys: {', '.join(missing)}", file=sys.stderr)
        return 1

    # --- step 2 - start - pass public browser configuration to later build steps
    if os.environ.get("GITHUB_ACTIONS") == "true":
        for key in ("VITE_GEOAPIFY_API_KEY", "VITE_CLERK_PUBLISHABLE_KEY"):
            print(f"::add-mask::{values[key]}")

    with output.open("a", encoding="utf-8") as github_env:
        for key in BUILD_KEYS:
            github_env.write(f"{key}={values[key]}\n")
    print("Loaded eight frontend build values from the target VM")
    # --- step 2 - end - pass public browser configuration to later build steps
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
