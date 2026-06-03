#!/usr/bin/env python3
"""
Verify EPIC-KITCHENS downloads produced by epic_downloader.py.

Example:
  python verify_epic_kitchens_download.py \
    --output-path /tx-NFS/public_datasets/raw/ \
    --participants P30,P31 \
    --videos

By default this verifies the same selection implied by:
  epic_downloader.py --videos --participants <...> --output-path <...>
namely all challenges/splits, both EPIC-55 and EPIC-100 extension videos.
"""

import argparse
import csv
import hashlib
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_EPIC55_SPLITS = "data/epic_55_splits.csv"
DEFAULT_EPIC100_SPLITS = "data/epic_100_splits.csv"
DEFAULT_MD5 = "data/md5.csv"
DEFAULT_ERRATA = "data/errata.csv"


def parse_bool(value):
    return str(value).lower().strip() in {"true", "yes", "y", "1"}


def normalize_participant(raw):
    """Accept P30, p30, P1, P01, 30, or 1; return PXX-style string."""
    s = str(raw).strip().upper()
    if not s:
        raise ValueError("empty participant value")
    if s.startswith("P"):
        s = s[1:]
    if not s.isdigit():
        raise ValueError(f"invalid participant {raw!r}; use P30, P01, P1, 30, or 1")
    n = int(s)
    if n <= 0:
        raise ValueError(f"invalid participant {raw!r}; participant number must be positive")
    return f"P{n:02d}"


def parse_csv_list(value, *, normalize=None):
    if value == "all":
        return "all"
    items = [x.strip() for x in str(value).split(",") if x.strip()]
    if not items:
        raise ValueError("empty comma-separated list")
    return [normalize(x) if normalize else x for x in items]


def md5_checksum(path, chunk_size=1024 * 1024 * 8):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def load_epic55_splits(path):
    video_to_split = {}
    with open(path, newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        require_columns(reader.fieldnames, {"video_id", "split"}, path)
        for row in reader:
            video_to_split[row["video_id"]] = row["split"]
    return video_to_split


def load_md5(path):
    checksums = {"55": {}, "100": {}, "errata": {}}
    with open(path, newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        require_columns(reader.fieldnames, {"version", "file_remote_path", "md5"}, path)
        for row in reader:
            version = row["version"]
            checksums.setdefault(version, {})[row["file_remote_path"]] = row["md5"].strip().lower()
    return checksums


def load_errata(path):
    if not path or not os.path.exists(path):
        return {}
    errata = {}
    with open(path, newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        require_columns(reader.fieldnames, {"rdsf_path", "dropbox_path"}, path)
        for row in reader:
            errata[row["rdsf_path"]] = row["dropbox_path"]
    return errata


def require_columns(fieldnames, required, path):
    fieldnames = set(fieldnames or [])
    missing = required - fieldnames
    if missing:
        raise ValueError(f"{path} is missing required column(s): {', '.join(sorted(missing))}")


def selected_split_columns(all_split_columns, splits, challenges):
    """Mimic epic_downloader.py split/challenge selection behavior."""
    if splits == "all" and challenges == "all":
        return list(all_split_columns)
    if splits == "all":
        return [cs for cs in all_split_columns for c in challenges if c == cs.split("_")[0]]
    if challenges == "all":
        return [cs for cs in all_split_columns for s in splits if s in cs.partition("_")[2]]
    return [
        cs
        for cs in all_split_columns
        for c in challenges
        for s in splits
        if c == cs.split("_")[0] and s in cs.partition("_")[2]
    ]


def collect_expected_videos(epic55_splits_path, epic100_splits_path, participants,
                            splits="all", challenges="all",
                            extension_only=False, epic55_only=False):
    epic55_splits = load_epic55_splits(epic55_splits_path)
    expected = {}

    with open(epic100_splits_path, newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        require_columns(reader.fieldnames, {"video_id"}, epic100_splits_path)
        all_split_columns = [f for f in reader.fieldnames if f != "video_id"]
        use_columns = selected_split_columns(all_split_columns, splits, challenges)
        if not use_columns:
            raise ValueError(
                "No split columns matched. Check --splits/--challenges against columns in "
                f"{epic100_splits_path}: {', '.join(all_split_columns)}"
            )

        participant_set = None if participants == "all" else set(participants)

        for row in reader:
            video_id = row["video_id"]
            parts = video_id.split("_")
            if len(parts) != 2:
                raise ValueError(f"Unexpected video_id format in {epic100_splits_path}: {video_id}")

            participant_str = parts[0]
            extension = len(parts[1]) == 3

            if participant_set is not None and participant_str not in participant_set:
                continue
            if extension_only and not extension:
                continue
            if epic55_only and extension:
                continue
            if not any(parse_bool(row.get(col, "")) for col in use_columns):
                continue

            epic55_split = None if extension else epic55_splits.get(video_id)
            if not extension and epic55_split is None:
                raise ValueError(f"{video_id} appears to be EPIC-55 but is missing from {epic55_splits_path}")

            expected[video_id] = {
                "video_id": video_id,
                "participant_str": participant_str,
                "extension": extension,
                "epic_55_split": epic55_split,
            }

    return dict(sorted(expected.items()))


def video_expected_paths(video, errata, checksums):
    video_id = video["video_id"]
    participant = video["participant_str"]
    filename = f"{video_id}.MP4"

    if video["extension"]:
        remote_parts = [participant, "videos", filename]
        version = "100"
    else:
        remote_parts = ["videos", video["epic_55_split"], participant, filename]
        version = "55"

    # epic_downloader.py always writes videos to <EPIC-KITCHENS>/<PXX>/videos/<video_id>.MP4
    output_parts = [participant, "videos", filename]
    remote_key = "/".join(remote_parts)

    if remote_key in errata:
        version = "errata"

    expected_md5 = checksums.get(version, {}).get(remote_key)
    return {
        "video_id": video_id,
        "participant": participant,
        "source": "EPIC-100-extension" if video["extension"] else "EPIC-55",
        "version": version,
        "remote_key": remote_key,
        "relative_path": os.path.join(*output_parts),
        "expected_md5": expected_md5,
    }


def resolve_epic_root(args):
    if args.epic_root:
        return os.path.abspath(args.epic_root)
    out = os.path.abspath(args.output_path)
    if os.path.basename(out.rstrip(os.sep)) == "EPIC-KITCHENS":
        return out
    return os.path.join(out, "EPIC-KITCHENS")


def verify_one(epic_root, item, check_md5=True):
    local_path = os.path.join(epic_root, item["relative_path"])
    result = dict(item)
    result["local_path"] = local_path
    result["size_bytes"] = ""
    result["actual_md5"] = ""

    if not os.path.exists(local_path):
        result["status"] = "MISSING"
        return result
    if not os.path.isfile(local_path):
        result["status"] = "NOT_A_FILE"
        return result

    size = os.path.getsize(local_path)
    result["size_bytes"] = str(size)
    if size == 0:
        result["status"] = "EMPTY"
        return result

    expected_md5 = result["expected_md5"]
    if not check_md5:
        result["status"] = "OK_EXISTS"
        return result
    if not expected_md5:
        result["status"] = "OK_UNCHECKED_NO_MD5"
        return result

    actual = md5_checksum(local_path)
    result["actual_md5"] = actual
    result["status"] = "OK" if actual == expected_md5.lower() else "BAD_MD5"
    return result


def write_report(path, rows):
    fieldnames = [
        "participant", "video_id", "source", "status", "relative_path", "local_path",
        "size_bytes", "expected_md5", "actual_md5", "version", "remote_key",
    ]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def print_summary(rows, *, max_list):
    by_participant = defaultdict(list)
    for row in rows:
        by_participant[row["participant"]].append(row)

    print("\nVerification summary")
    print("====================")
    for participant in sorted(by_participant):
        participant_rows = by_participant[participant]
        counts = Counter(r["status"] for r in participant_rows)
        ok_count = counts.get("OK", 0) + counts.get("OK_EXISTS", 0) + counts.get("OK_UNCHECKED_NO_MD5", 0)
        problem_count = len(participant_rows) - ok_count
        print(f"\n{participant}: expected={len(participant_rows)} ok={ok_count} problems={problem_count}")
        for status in sorted(counts):
            print(f"  {status}: {counts[status]}")

        bad_rows = [r for r in participant_rows if not r["status"].startswith("OK")]
        for r in bad_rows[:max_list]:
            print(f"  - {r['status']}: {r['relative_path']}")
        if len(bad_rows) > max_list:
            print(f"  ... {len(bad_rows) - max_list} more problem file(s) omitted; use --report for full list")


def create_parser():
    p = argparse.ArgumentParser(
        description="Verify EPIC-KITCHENS downloads for selected participants using the official split and md5 CSVs."
    )
    location = p.add_mutually_exclusive_group()
    location.add_argument(
        "--output-path",
        default="/tx-NFS/public_datasets/raw/",
        help="The same base path passed to epic_downloader.py. EPIC-KITCHENS is appended if needed."
    )
    location.add_argument(
        "--epic-root",
        help="Path to the EPIC-KITCHENS directory itself, e.g. /tx-NFS/public_datasets/raw/EPIC-KITCHENS."
    )

    p.add_argument("--participants", default="P30,P31",
                   help="Comma-separated participants: P30,P31,P1 or 30,31,1. Use 'all' for all participants.")
    p.add_argument("--videos", action="store_true",
                   help="Verify videos. Present for symmetry with the downloader; videos are the only supported item here.")
    p.add_argument("--splits", default="all",
                   help="Comma-separated split filters, or all. Defaults to all, matching the shown downloader command.")
    p.add_argument("--challenges", default="all",
                   help="Comma-separated challenge filters such as ar,da,cmr, or all. Defaults to all.")
    p.add_argument("--extension-only", action="store_true", help="Only verify EPIC-100 extension videos.")
    p.add_argument("--epic55-only", action="store_true", help="Only verify EPIC-55 videos.")

    p.add_argument("--epic55-splits", default=DEFAULT_EPIC55_SPLITS,
                   help=f"Path to epic_55_splits.csv. Default: {DEFAULT_EPIC55_SPLITS}")
    p.add_argument("--epic100-splits", default=DEFAULT_EPIC100_SPLITS,
                   help=f"Path to epic_100_splits.csv. Default: {DEFAULT_EPIC100_SPLITS}")
    p.add_argument("--md5", default=DEFAULT_MD5,
                   help=f"Path to md5.csv. Default: {DEFAULT_MD5}")
    p.add_argument("--errata", default=DEFAULT_ERRATA,
                   help=f"Path to errata.csv. Default: {DEFAULT_ERRATA}. If missing, errata are ignored.")

    p.add_argument("--no-md5", action="store_true",
                   help="Only check that expected files exist and are non-empty; much faster but less strict.")
    p.add_argument("--report", help="Optional CSV path for a full per-file verification report.")
    p.add_argument("--max-list", type=int, default=30,
                   help="Maximum problem files to print per participant. Default: 30.")
    return p


def main(argv=None):
    args = create_parser().parse_args(argv)

    if args.extension_only and args.epic55_only:
        print("ERROR: choose at most one of --extension-only and --epic55-only", file=sys.stderr)
        return 2

    try:
        participants = parse_csv_list(args.participants, normalize=normalize_participant)
        splits = parse_csv_list(args.splits)
        challenges = parse_csv_list(args.challenges)
        epic_root = resolve_epic_root(args)

        expected_videos = collect_expected_videos(
            args.epic55_splits,
            args.epic100_splits,
            participants,
            splits=splits,
            challenges=challenges,
            extension_only=args.extension_only,
            epic55_only=args.epic55_only,
        )
        checksums = load_md5(args.md5)
        errata = load_errata(args.errata)

        expected_items = [video_expected_paths(v, errata, checksums) for v in expected_videos.values()]
        if not expected_items:
            print("No expected videos matched your filters. Check --participants/--splits/--challenges.", file=sys.stderr)
            return 2

        print(f"EPIC root: {epic_root}")
        print(f"Expected video files: {len(expected_items)}")
        print(f"MD5 checking: {'disabled' if args.no_md5 else 'enabled'}")

        rows = [verify_one(epic_root, item, check_md5=not args.no_md5) for item in expected_items]
        print_summary(rows, max_list=args.max_list)

        if args.report:
            write_report(args.report, rows)
            print(f"\nWrote report: {args.report}")

        problem_statuses = {"MISSING", "NOT_A_FILE", "EMPTY", "BAD_MD5"}
        return 1 if any(r["status"] in problem_statuses for r in rows) else 0

    except BrokenPipeError:
        return 1
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
