#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the vLLM project
"""
Script to organize wheels by size for GitHub Pages (<100MB) and GitHub Releases (>100MB).
Optimized for minimal disk space usage using move + symlinks.
"""

import os
import sys
import shutil
import time
from pathlib import Path
from datetime import datetime

SIZE_LIMIT = 100 * 1024 * 1024  # 100MB

# Validate environment
print("Validating environment...")
if 'GITHUB_OUTPUT' not in os.environ:
    print("ERROR: GITHUB_OUTPUT environment variable not set!", file=sys.stderr)
    print("This script must be run in a GitHub Actions environment.", file=sys.stderr)
    sys.exit(1)
print(f"GITHUB_OUTPUT is set to: {os.environ['GITHUB_OUTPUT']}")

# Validate artifacts directory exists
artifacts_dir = Path("artifacts")
print(f"\nChecking for artifacts directory at: {artifacts_dir.absolute()}")

if not artifacts_dir.exists():
    print(f"ERROR: Artifacts directory not found at: {artifacts_dir.absolute()}", file=sys.stderr)
    print(f"\nCurrent working directory: {Path.cwd()}", file=sys.stderr)
    print(f"\nContents of current directory:", file=sys.stderr)
    for item in sorted(Path.cwd().iterdir()):
        print(f"  - {item.name}", file=sys.stderr)
    sys.exit(1)

if not artifacts_dir.is_dir():
    print(f"ERROR: {artifacts_dir} exists but is not a directory!", file=sys.stderr)
    sys.exit(1)

print(f"Artifacts directory found: {artifacts_dir.absolute()}")

# Create directories
packages_dir = Path("pypi-repo/packages")
large_dir = Path("pypi-repo/packages-large")
small_dir = Path("pypi-repo/packages-small")

print("\nCreating output directories...")
packages_dir.mkdir(parents=True, exist_ok=True)
large_dir.mkdir(parents=True, exist_ok=True)
small_dir.mkdir(parents=True, exist_ok=True)
print(f"  - {packages_dir}")
print(f"  - {large_dir}")
print(f"  - {small_dir}")

# Find all wheels
print("\nCollecting wheels from artifacts...")
print(f"Searching in: {artifacts_dir.absolute()}")
all_wheels = list(artifacts_dir.rglob("*.whl"))
total = len(all_wheels)

if total == 0:
    print(f"\nWARNING: No wheels found in {artifacts_dir}/", file=sys.stderr)
    print(f"\nArtifacts directory structure:", file=sys.stderr)
    items_found = False
    for item in artifacts_dir.rglob("*"):
        if item.is_file():
            items_found = True
            print(f"  {item.relative_to(artifacts_dir)}", file=sys.stderr)
    if not items_found:
        print("  (directory is empty)", file=sys.stderr)
    print(f"\nERROR: Cannot proceed without any wheels!", file=sys.stderr)
    sys.exit(1)

print(f"Found {total} wheels to process")

# Check disk space (optimized calculation for move+symlink approach)
total_wheel_size = sum(w.stat().st_size for w in all_wheels)
stat = shutil.disk_usage(".")
free_gb = stat.free / (1024**3)

# With copy approach, we need 2x the wheel size for small wheels
# (packages/ + packages-small/ both contain actual files)
needed_gb = total_wheel_size / (1024**3) * 2.0  # 2x for dual storage

print(f"\nDisk Space Check:")
print(f"  Total wheel size: {total_wheel_size/(1024**3):.2f} GB")
print(f"  Available space: {free_gb:.2f} GB")
print(f"  Estimated needed: {needed_gb:.2f} GB (using copy for dumb-pypi compatibility)")

if free_gb < needed_gb:
    print(f"\nERROR: Insufficient disk space!", file=sys.stderr)
    print(f"Need {needed_gb:.2f}GB but only {free_gb:.2f}GB available", file=sys.stderr)
    sys.exit(1)

print("Disk space check: OK\n")

# Process wheels with OPTIMIZED approach: move + symlink
print(f"{'='*70}")
print("Processing wheels (using move + symlink for space efficiency)...")
print(f"{'='*70}\n")

large_count = 0
small_count = 0
large_total_size = 0
small_total_size = 0
start_time = time.time()
last_progress_time = start_time

for i, wheel in enumerate(all_wheels, 1):
    try:
        size = wheel.stat().st_size
        size_mb = size / (1024*1024)

        # Determine destination(s) and move/symlink
        if size > SIZE_LIMIT:
            # Large wheels: MOVE to packages-large/ (frees space from artifacts/)
            dest = large_dir / wheel.name
            shutil.move(str(wheel), str(dest))
            large_count += 1
            large_total_size += size
            operation = "moved -> packages-large/"
        else:
            # Small wheels: MOVE to packages/, COPY to packages-small/
            # Using actual files (not symlinks) for dumb-pypi compatibility
            primary_dest = packages_dir / wheel.name
            small_dest = small_dir / wheel.name

            # Move to primary location (packages/)
            shutil.move(str(wheel), str(primary_dest))

            # Copy to packages-small/ for dumb-pypi indexing
            # dumb-pypi cannot process symlinks, needs actual files
            shutil.copy2(str(primary_dest), str(small_dest))

            small_count += 1
            small_total_size += size
            operation = "moved -> packages/ + copied -> packages-small/"

        # Enhanced progress indicator
        current_time = time.time()
        elapsed = current_time - start_time
        time_since_last = current_time - last_progress_time

        # Show progress for: every 10 wheels, large files, last wheel, or every 30 seconds
        show_progress = (
            i % 10 == 0 or
            i == total or
            size > SIZE_LIMIT or
            time_since_last > 30
        )

        if show_progress:
            rate = i / elapsed if elapsed > 0 else 0
            eta_seconds = (total - i) / rate if rate > 0 else 0
            pct = i * 100 // total

            # Truncate filename if too long
            display_name = wheel.name[:50] + "..." if len(wheel.name) > 53 else wheel.name

            print(f"[{elapsed:.0f}s] {i}/{total} ({pct}%) | "
                  f"{display_name} ({size_mb:.1f}MB) | "
                  f"Rate: {rate:.2f}/s | ETA: {eta_seconds:.0f}s")

            last_progress_time = current_time

    except Exception as e:
        print(f"WARNING: Failed to process {wheel.name}: {e}", file=sys.stderr)

total_time = time.time() - start_time

# Verify artifacts directory is now empty (all files moved)
remaining_wheels = list(artifacts_dir.rglob("*.whl"))
if remaining_wheels:
    print(f"\nWARNING: {len(remaining_wheels)} wheels remain in artifacts/", file=sys.stderr)
else:
    print(f"\nArtifacts directory cleaned: all wheels moved successfully")

# Summary
print(f"\n{'='*70}")
print(f"Wheel Organization Complete!")
print(f"{'='*70}")
print(f"Total wheels processed: {total}")
print(f"  Large wheels (>100MB): {large_count} -> GitHub Releases ({large_total_size/(1024**3):.2f} GB)")
print(f"  Small wheels (<100MB): {small_count} -> GitHub Pages ({small_total_size/(1024**2):.1f} MB)")
print(f"Total processing time: {total_time:.1f} seconds")
print(f"Average rate: {total/total_time:.2f} wheels/second")
print(f"\nDisk space usage: Using copy approach for dumb-pypi compatibility")
print(f"  Actual space used: ~{total_wheel_size*2/(1024**3):.2f} GB")
print(f"  Small wheels are in both packages/ and packages-small/ (actual files, not symlinks)")
print(f"{'='*70}\n")

# List examples
large_wheels = sorted(large_dir.glob("*.whl"), key=lambda x: x.stat().st_size, reverse=True)
if large_wheels:
    print(f"Largest wheels (showing {min(5, len(large_wheels))} of {len(large_wheels)}):")
    for w in large_wheels[:5]:
        size_mb = w.stat().st_size / (1024*1024)
        print(f"  - {w.name} ({size_mb:.1f} MB)")

small_sample = list(small_dir.glob("*.whl"))[:5]
if small_sample:
    print(f"\nSmall wheels sample (showing 5 of {small_count}):")
    for w in small_sample:
        size_mb = w.stat().st_size / (1024*1024)
        print(f"  - {w.name} ({size_mb:.1f} MB)")

# Set output for next steps
release_tag = f"wheels-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

print(f"\nSetting GitHub Actions output...")
try:
    with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
        f.write(f"release_tag={release_tag}\n")
    print(f"Release tag set: {release_tag}")
    print(f"Successfully wrote to GITHUB_OUTPUT")
except Exception as e:
    print(f"\nERROR: Failed to write to GITHUB_OUTPUT: {e}", file=sys.stderr)
    sys.exit(1)

print("\nScript completed successfully!")
