#!/usr/bin/env python3

#####
#
# Auto-updater that checks the installed Soloist's age, and if it exceeds
# a certain age, stops the running Soloist service, downloads and extracts
# a new Soloist build, replaces the existing one, and starts the service again.
#
# It can be forced to update by using --force
# It can be prevented from doing any changes by using --dry-run
#
#####


import os
import subprocess
import tempfile
import urllib.request
import re
import argparse
import logging
import platform
from pathlib import Path
import time
from math import trunc

INSTALL_DIR = Path("/usr/local/lib/soloist")
BINARY = INSTALL_DIR / "soloist"
BACKUP = INSTALL_DIR / "soloist.old"
SERVICE = "soloist.service"
UPDATE_INTERVAL = 60 * 60 * 24 * 60  # 60 days in seconds
VERSION_REGEX = re.compile(
    r"^soloist "
    r"(?P<version>\d+(?:\.\d+)+) "
    r"build (?P<build_timestamp>\d+) "
    r"\((?P<build_date>\d{8})\)"
)
ARCH = {
    "armv6l": "arm32",
    "armv7l": "arm32",
    "aarch64": "arm64",
    "x86_64": "x86_64",
}[platform.machine()]

parser = argparse.ArgumentParser()
parser.add_argument("--force", action="store_true", help="Force the update even if the current version is up to date")
parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def get_build_time(version_string: str) -> float:
    match = VERSION_REGEX.match(version_string)
    if match is None:
        raise ValueError(f"{version_string} is not a valid version")
    return float(match.groupdict()["build_timestamp"])


def existing() -> str:
    version = subprocess.run([BINARY, "--version"], check=True, capture_output=True, text=True).stdout.strip()
    logger.info("Existing version: %s", version)
    return version


def download(tmp: Path) -> Path:
    url = f"https://soloist-builds.spotifycdn.com/soloist_release_{ARCH}.tar.gz"
    archive = tmp / "soloist.tar.gz"
    urllib.request.urlretrieve(url, archive)
    return archive


def extract(archive: Path) -> Path:
    extracted = archive.parent / "extracted"
    extracted.mkdir()

    subprocess.run(["tar", "xzf", archive, "-C", extracted], check=True)
    binary = extracted / "soloist"

    if not binary.exists():
        raise RuntimeError("Downloaded archive does not contain soloist")

    return binary


def start_service(service: str):
    subprocess.run(["systemctl", "start", service], check=True)


def stop_service(service: str):
    subprocess.run(["systemctl", "stop", service], check=True)


def update(old: Path, new: Path, backup: Path | None = None):
    if backup is not None:
        os.replace(old, backup)
    os.replace(new, old)


def rollback(binary: Path):
    os.replace(binary, BINARY)


def main(*, force: bool = False, dry_run: bool = False):
    if dry_run:
        logger.info("This is a dry run")

    old_version = existing()
    old_version_timestamp = get_build_time(old_version)
    now = time.time()

    if force:
        logger.info("Forced mode; update needed")
    elif (age := now - old_version_timestamp) >= UPDATE_INTERVAL:
        logger.info("Age %s days; update needed", trunc(age / (24 * 60 * 60)))
    else:
        logger.info("Age %s days; no update needed", trunc(age / (24 * 60 * 60)))
        return

    # Can't use /tmp because it's on a different filesystem, so os.replace()
    # won't work:
    with tempfile.TemporaryDirectory(dir=INSTALL_DIR) as tmp:
        logger.info("Downloading Soloist to %s...", tmp)
        archive = download(Path(tmp))

        logger.info("Extracting %s...", archive)
        new_binary = extract(archive)

        # Check new binary will run
        new_version = subprocess.run([new_binary, "--version"], check=True, capture_output=True, text=True).stdout.strip()

        if VERSION_REGEX.match(new_version) is not None:
            logger.info("Checked new binary is executable: successful. New version is %s", new_version)
        else:
            raise RuntimeError("Checked new binary is executable: failure")

        if dry_run:
            logger.info("This is a dry run, exiting now")
            return

        logger.info("Stopping service %s...", SERVICE)
        stop_service(SERVICE)

        try:
            logger.info("Installing new binary...")
            update(BINARY, new_binary, BACKUP)

            logger.info("Starting service %s...", SERVICE)
            start_service(SERVICE)

        except Exception as e:
            logger.error("Installation failed: %s. Rolling back update.", e)
            rollback(BACKUP)

            logger.info("Starting service %s...", SERVICE)
            start_service(SERVICE)
            
            raise

        else:
            BACKUP.unlink()


if __name__ == "__main__":
    args = parser.parse_args()

    try:
        main(force=args.force, dry_run=args.dry_run)
    except Exception:
        logger.exception("Update failed")
        raise
