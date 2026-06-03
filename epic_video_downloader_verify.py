#!/usr/bin/env python3
"""
EPIC-KITCHENS video downloader with progress + verification.

What it does:
  1. Reads the same EPIC metadata CSVs used by epic_downloader.py.
  2. Selects videos for participants such as P30,P31 or P1/P01/1.
  3. Downloads each expected MP4 to <output-path>/EPIC-KITCHENS/<participant>/videos/<video_id>.MP4.
  4. Verifies each file with MD5 from data/md5.csv when available.
  5. If a file is missing or incomplete/corrupt, downloads it again.
  6. Shows progress, speed, elapsed time, and ETA while downloading and verifying.

Default behavior:
  - Complete files are skipped after MD5 verification.
  - Bad/incomplete files are replaced only after a newly downloaded .part file verifies OK.
  - Interrupted .part downloads are resumed with HTTP Range when the server supports it;
    otherwise the script restarts that file from byte 0.

Example:
  python epic_video_downloader_verify.py \
    --participants P01 \
    --output-path /tx-NFS/public_datasets/raw/ \
    --max-retries 3 \
    --report epic_download_report_P01.csv
"""

import argparse
import csv
import hashlib
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


EPIC_55_BASE_URL = "https://data.bris.ac.uk/datasets/3h91syskeag572hl6tvuovwv4d"
EPIC_100_BASE_URL = "https://data.bris.ac.uk/datasets/2g1n6qdydwa9u22shpxqzp0t8m"
DEFAULT_CHUNK_SIZE = 8 * 1024 * 1024  # 8 MiB
USER_AGENT = "epic-kitchens-video-downloader/1.0"


# ----------------------------- formatting helpers -----------------------------

def human_bytes(num):
    if num is None:
        return "?"
    num = float(num)
    for unit in ["B", "KiB", "MiB", "GiB", "TiB"]:
        if abs(num) < 1024.0 or unit == "TiB":
            if unit == "B":
                return f"{int(num)} {unit}"
            return f"{num:.2f} {unit}"
        num /= 1024.0


def format_duration(seconds):
    if seconds is None or seconds < 0 or seconds == float("inf"):
        return "?"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def truncate_middle(text, max_len):
    if len(text) <= max_len:
        return text
    if max_len <= 10:
        return text[:max_len]
    left = (max_len - 3) // 2
    right = max_len - 3 - left
    return text[:left] + "..." + text[-right:]


class ProgressPrinter:
    def __init__(self, label, total=None, stream=None):
        self.label = label
        self.total = total
        self.stream = stream or sys.stderr
        self.start = time.monotonic()
        self.last_print = 0.0
        self.last_done = 0

    def update(self, done, force=False):
        now = time.monotonic()
        if not force and now - self.last_print < 0.20 and done != self.total:
            return
        self.last_print = now
        self.last_done = done

        elapsed = max(now - self.start, 1e-9)
        speed = done / elapsed
        eta = None
        if self.total and speed > 0 and done <= self.total:
            eta = (self.total - done) / speed

        width = 100
        try:
            width = os.get_terminal_size().columns
        except OSError:
            pass

        prefix = truncate_middle(self.label, 32)
        if self.total:
            pct = min(max(done / self.total, 0.0), 1.0)
            bar_len = 24
            filled = int(bar_len * pct)
            if filled >= bar_len:
                bar = "=" * bar_len
            else:
                bar = "=" * filled + ">" + "." * (bar_len - filled - 1)
            line = (
                f"\r{prefix} [{bar}] {pct * 100:6.2f}% "
                f"{human_bytes(done)}/{human_bytes(self.total)} "
                f"| {human_bytes(speed)}/s | ETA {format_duration(eta)} "
                f"| elapsed {format_duration(elapsed)}"
            )
        else:
            line = (
                f"\r{prefix} {human_bytes(done)} "
                f"| {human_bytes(speed)}/s | elapsed {format_duration(elapsed)}"
            )

        if len(line) >= width:
            line = line[: max(0, width - 1)]
        self.stream.write(line)
        self.stream.flush()

    def finish(self, done=None):
        if done is None:
            done = self.last_done
        self.update(done, force=True)
        self.stream.write("\n")
        self.stream.flush()


# ----------------------------- metadata helpers -----------------------------

def parse_bool(value):
    return str(value).strip().lower() in {"true", "yes", "y", "1"}


def normalize_participant(value):
    """Accept 1, P1, P01, P30 and return P01, P01, P01, P30."""
    value = str(value).strip().upper()
    if not value:
        raise ValueError("empty participant id")
    if value.startswith("P"):
        number = int(value[1:])
    else:
        number = int(value)
    if number <= 0:
        raise ValueError(f"invalid participant id: {value}")
    return f"P{number:02d}"


def parse_participant_list(value):
    if value is None or str(value).strip().lower() == "all":
        return None
    return {normalize_participant(x) for x in str(value).split(",") if x.strip()}


def normalize_video_id(value):
    """Accept P1_01 / P01_01 / P30_101 and return normalized video id."""
    value = str(value).strip().upper()
    if "_" not in value:
        raise ValueError(f"invalid video id: {value}; expected something like P30_01")
    participant, suffix = value.split("_", 1)
    return f"{normalize_participant(participant)}_{suffix}"


def parse_csv_list(value):
    if value is None or str(value).strip().lower() == "all":
        return None
    return [x.strip() for x in str(value).split(",") if x.strip()]


def parse_video_list(value):
    if value is None or str(value).strip().lower() == "all":
        return None
    return {normalize_video_id(x) for x in str(value).split(",") if x.strip()}


def load_md5(md5_path):
    md5 = {"55": {}, "100": {}, "errata": {}}
    with open(md5_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            version = row["version"]
            md5.setdefault(version, {})[row["file_remote_path"]] = row["md5"].strip().lower()
    return md5


def load_errata(errata_path):
    errata = {}
    if not errata_path or not Path(errata_path).exists():
        return errata
    with open(errata_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            errata[row["rdsf_path"]] = row["dropbox_path"]
    return errata


class EpicVideoCatalog:
    def __init__(self, epic55_splits_path, epic100_splits_path):
        self.epic55_splits_path = Path(epic55_splits_path)
        self.epic100_splits_path = Path(epic100_splits_path)
        self.epic55_video_to_split = {}
        self.challenges_splits = []
        self.videos_per_split = {}
        self._load()

    def _load(self):
        with open(self.epic55_splits_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.epic55_video_to_split[row["video_id"].strip().upper()] = row["split"].strip()

        with open(self.epic100_splits_path, newline="") as f:
            reader = csv.DictReader(f)
            self.challenges_splits = [name for name in reader.fieldnames if name != "video_id"]
            self.videos_per_split = {name: [] for name in self.challenges_splits}

            for row in reader:
                video_id = row["video_id"].strip().upper()
                parts = video_id.split("_")
                if len(parts) != 2:
                    continue
                participant = normalize_participant(parts[0])
                # Original downloader treats 3-digit suffixes as EPIC-100 extension videos.
                extension = len(parts[1]) == 3
                epic55_split = None if extension else self.epic55_video_to_split.get(video_id)
                video = {
                    "video_id": video_id,
                    "participant_str": participant,
                    "participant_num": int(participant[1:]),
                    "extension": extension,
                    "epic55_split": epic55_split,
                }
                for split_name in self.challenges_splits:
                    if parse_bool(row.get(split_name, "")):
                        self.videos_per_split[split_name].append(video)

    def choose_split_columns(self, challenges=None, splits=None):
        """
        Mirrors the original script's challenge/split filtering style.
        challenges: None means all, otherwise e.g. ['ar', 'da', 'cmr'].
        splits: None means all, otherwise e.g. ['train', 'val', 'test'].
        """
        if challenges is None and splits is None:
            return list(self.challenges_splits)

        chosen = []
        for col in self.challenges_splits:
            challenge_name = col.split("_")[0]
            split_name = col.partition("_")[2]

            challenge_ok = True if challenges is None else any(c == challenge_name for c in challenges)
            split_ok = True if splits is None else any(s in split_name for s in splits)
            if challenge_ok and split_ok:
                chosen.append(col)
        return chosen

    def select_videos(
        self,
        participants=None,
        specific_videos=None,
        challenges=None,
        splits=None,
        extension_only=False,
        epic55_only=False,
    ):
        selected = {}
        for split_col in self.choose_split_columns(challenges=challenges, splits=splits):
            for video in self.videos_per_split[split_col]:
                if extension_only and not video["extension"]:
                    continue
                if epic55_only and video["extension"]:
                    continue

                add = False
                if participants is None and specific_videos is None:
                    add = True
                if participants is not None and video["participant_str"] in participants:
                    add = True
                if specific_videos is not None and video["video_id"] in specific_videos:
                    add = True

                if add:
                    selected[video["video_id"]] = video

        return [selected[k] for k in sorted(selected)]


# ----------------------------- URL/path helpers -----------------------------

def remote_parts_for_video(video):
    filename = f"{video['video_id']}.MP4"
    if video["extension"]:
        return [video["participant_str"], "videos", filename]
    if not video["epic55_split"]:
        raise ValueError(f"missing EPIC-55 split for {video['video_id']}")
    return ["videos", video["epic55_split"], video["participant_str"], filename]


def output_path_for_video(base_output, video):
    # This matches the original downloader's local layout for videos:
    # <output>/EPIC-KITCHENS/<participant>/videos/<video_id>.MP4
    return Path(base_output) / "EPIC-KITCHENS" / video["participant_str"] / "videos" / f"{video['video_id']}.MP4"


def build_download_item(video, output_base, md5, errata, epic55_base, epic100_base):
    remote_parts = remote_parts_for_video(video)
    remote_key = "/".join(remote_parts)
    erratum_url = errata.get(remote_key)

    if erratum_url:
        url = erratum_url
        version = "errata"
        source = "errata"
    else:
        version = "100" if video["extension"] else "55"
        base_url = epic100_base.rstrip("/") if video["extension"] else epic55_base.rstrip("/")
        url = "/".join([base_url] + remote_parts)
        source = f"EPIC-{version}"

    expected_md5 = md5.get(version, {}).get(remote_key)
    return {
        "video_id": video["video_id"],
        "participant": video["participant_str"],
        "extension": video["extension"],
        "source": source,
        "version": version,
        "remote_key": remote_key,
        "url": url,
        "path": output_path_for_video(output_base, video),
        "expected_md5": expected_md5,
    }


# ----------------------------- verification + download -----------------------------

def md5_checksum(path, label=None, show_progress=True, chunk_size=DEFAULT_CHUNK_SIZE):
    path = Path(path)
    total = path.stat().st_size
    progress = ProgressPrinter(label or f"MD5 {path.name}", total=total) if show_progress else None
    h = hashlib.md5()
    done = 0
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
            done += len(chunk)
            if progress:
                progress.update(done)
    if progress:
        progress.finish(done)
    return h.hexdigest().lower()


def verify_file(path, expected_md5=None, show_progress=True):
    path = Path(path)
    if not path.exists():
        return False, "missing", None
    if not path.is_file():
        return False, "not_a_file", None
    if path.stat().st_size <= 0:
        return False, "empty_file", None

    if expected_md5:
        digest = md5_checksum(path, label=f"MD5 {path.name}", show_progress=show_progress)
        if digest == expected_md5.lower():
            return True, "ok", digest
        return False, "bad_md5", digest

    # Fallback when metadata has no MD5. This is weaker than MD5 verification.
    return True, "exists_no_md5", None


def parse_content_length(headers):
    value = headers.get("Content-Length")
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def parse_total_from_content_range(headers):
    # Example: Content-Range: bytes 100-999/1000
    value = headers.get("Content-Range")
    if not value:
        return None
    match = re.search(r"/([0-9]+)\s*$", value)
    if not match:
        return None
    return int(match.group(1))


def make_request(url, start_byte=None):
    headers = {"User-Agent": USER_AGENT}
    if start_byte is not None and start_byte > 0:
        headers["Range"] = f"bytes={start_byte}-"
    return urllib.request.Request(url, headers=headers)


def download_to_part_file(url, part_path, label, context, timeout, chunk_size, resume=True):
    part_path = Path(part_path)
    part_path.parent.mkdir(parents=True, exist_ok=True)

    existing = part_path.stat().st_size if resume and part_path.exists() else 0
    request = make_request(url, start_byte=existing if existing > 0 else None)

    try:
        response = urllib.request.urlopen(request, timeout=timeout, context=context)
    except urllib.error.HTTPError as e:
        # Range Not Satisfiable: probably a stale/corrupt .part. Restart cleanly.
        if existing > 0 and e.code == 416:
            print(f"Range resume rejected for {part_path.name}; restarting from byte 0.")
            part_path.unlink(missing_ok=True)
            request = make_request(url)
            response = urllib.request.urlopen(request, timeout=timeout, context=context)
        else:
            raise

    with response:
        status = getattr(response, "status", response.getcode())
        headers = response.headers
        content_length = parse_content_length(headers)

        if existing > 0 and status == 206:
            mode = "ab"
            start_done = existing
            total = parse_total_from_content_range(headers)
            if total is None and content_length is not None:
                total = existing + content_length
            print(f"Resuming {part_path.name} from {human_bytes(existing)}")
        else:
            if existing > 0:
                print(f"Server did not accept resume for {part_path.name}; restarting from byte 0.")
            mode = "wb"
            start_done = 0
            total = content_length

        progress = ProgressPrinter(label, total=total)
        done = start_done
        progress.update(done, force=True)

        with open(part_path, mode) as f:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                progress.update(done)

        progress.finish(done)
        return done, total


def ensure_downloaded(item, args, context, index, total_items):
    path = Path(item["path"])
    expected_md5 = item["expected_md5"]
    label_base = f"[{index}/{total_items}] {item['video_id']}.MP4"

    print("\n" + "=" * 90)
    print(f"Video:       {item['video_id']}")
    print(f"Participant: {item['participant']}")
    print(f"Source:      {item['source']}")
    print(f"Remote key:  {item['remote_key']}")
    print(f"Output:      {path}")
    print(f"Expected MD5:{' ' + expected_md5 if expected_md5 else ' <not found in md5.csv>'}")

    ok, reason, digest = verify_file(path, expected_md5, show_progress=not args.no_md5_progress)
    if ok:
        print(f"Status:      OK ({reason}); skipping download.")
        return {"video_id": item["video_id"], "status": "ok", "reason": reason, "path": str(path)}

    print(f"Status:      needs download ({reason}).")
    if digest:
        print(f"Local MD5:   {digest}")

    part_path = Path(str(path) + ".part")
    last_error = None
    for attempt in range(1, args.max_retries + 1):
        print(f"Attempt:     {attempt}/{args.max_retries}")
        try:
            download_to_part_file(
                url=item["url"],
                part_path=part_path,
                label=f"{label_base} download",
                context=context,
                timeout=args.timeout,
                chunk_size=args.chunk_size,
                resume=not args.no_resume_part,
            )

            tmp_ok, tmp_reason, tmp_digest = verify_file(
                part_path, expected_md5, show_progress=not args.no_md5_progress
            )

            if tmp_ok:
                path.parent.mkdir(parents=True, exist_ok=True)
                os.replace(part_path, path)
                print(f"Verified:    OK ({tmp_reason})")
                print(f"Saved:       {path}")
                return {"video_id": item["video_id"], "status": "downloaded", "reason": tmp_reason, "path": str(path)}

            print(f"Verify fail: {tmp_reason}")
            if tmp_digest:
                print(f"Downloaded MD5: {tmp_digest}")
            # If the full downloaded file is bad, do not keep appending to it.
            if part_path.exists():
                part_path.unlink()
            last_error = RuntimeError(f"verification failed: {tmp_reason}")

        except KeyboardInterrupt:
            print("\nInterrupted. Partial .part file was kept for possible resume.")
            raise
        except Exception as e:  # keep .part for resume on transient network errors
            last_error = e
            print(f"Error:       {e}")
            if attempt < args.max_retries:
                sleep_s = min(30, 2 * attempt)
                print(f"Retrying after {sleep_s}s...")
                time.sleep(sleep_s)

    return {
        "video_id": item["video_id"],
        "status": "failed",
        "reason": str(last_error) if last_error else "unknown",
        "path": str(path),
    }


def write_report(path, records):
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["video_id", "status", "reason", "path"])
        writer.writeheader()
        writer.writerows(records)
    print(f"Report written: {report_path}")


# ----------------------------- CLI -----------------------------

def build_parser():
    p = argparse.ArgumentParser(
        description="Download EPIC-KITCHENS participant videos with progress and MD5 verification."
    )
    p.add_argument("--participants", default="all", help="Participant IDs, e.g. P30,P31 or P1 or 1. Default: all")
    p.add_argument("--specific-videos", default="all", help="Video IDs, e.g. P30_01,P30_02. Default: all")
    p.add_argument("--output-path", default=str(Path.home()), help="Base output path. EPIC-KITCHENS is appended.")

    p.add_argument("--epic55-splits", default="data/epic_55_splits.csv", help="Path to epic_55_splits.csv")
    p.add_argument("--epic100-splits", default="data/epic_100_splits.csv", help="Path to epic_100_splits.csv")
    p.add_argument("--md5", default="data/md5.csv", help="Path to md5.csv")
    p.add_argument("--errata", default="data/errata.csv", help="Path to errata.csv")

    p.add_argument("--epic55-base-url", default=EPIC_55_BASE_URL, help="EPIC-55 base URL")
    p.add_argument("--epic100-base-url", default=EPIC_100_BASE_URL, help="EPIC-100 base URL")

    p.add_argument("--challenges", default="all", help="Comma list: ar,da,cmr, or all. Default: all")
    p.add_argument("--splits", default="all", help="Comma list: train,val,test,source_train,..., or all. Default: all")
    p.add_argument("--extension-only", action="store_true", help="Only download EPIC-100 extension videos")
    p.add_argument("--epic55-only", action="store_true", help="Only download EPIC-55 videos")

    p.add_argument("--max-retries", type=int, default=3, help="Retries per video. Default: 3")
    p.add_argument("--timeout", type=int, default=120, help="Network timeout seconds. Default: 120")
    p.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE, help="Read chunk size in bytes. Default: 8388608")
    p.add_argument("--no-resume-part", action="store_true", help="Do not resume existing .part files; restart them")
    p.add_argument("--no-md5-progress", action="store_true", help="Do not show progress while calculating MD5")
    p.add_argument("--verify-ssl", action="store_true", help="Verify SSL certificates. Default matches original script: unverified SSL")
    p.add_argument("--report", default=None, help="Optional CSV report path")
    return p


def validate_args(args):
    if args.extension_only and args.epic55_only:
        raise SystemExit("Choose either --extension-only or --epic55-only, not both.")
    for name in ["epic55_splits", "epic100_splits", "md5"]:
        value = getattr(args, name)
        if not Path(value).exists():
            raise SystemExit(f"Required metadata file not found: {value}")
    if args.max_retries < 1:
        raise SystemExit("--max-retries must be >= 1")
    if args.chunk_size <= 0:
        raise SystemExit("--chunk-size must be > 0")


def main(argv=None):
    args = build_parser().parse_args(argv)
    validate_args(args)

    participants = parse_participant_list(args.participants)
    specific_videos = parse_video_list(args.specific_videos)
    challenges = parse_csv_list(args.challenges)
    splits = parse_csv_list(args.splits)

    context = ssl.create_default_context() if args.verify_ssl else ssl._create_unverified_context()

    catalog = EpicVideoCatalog(args.epic55_splits, args.epic100_splits)
    md5 = load_md5(args.md5)
    errata = load_errata(args.errata)

    videos = catalog.select_videos(
        participants=participants,
        specific_videos=specific_videos,
        challenges=challenges,
        splits=splits,
        extension_only=args.extension_only,
        epic55_only=args.epic55_only,
    )

    if not videos:
        print("No matching videos found. Check --participants, --specific-videos, --challenges, and --splits.")
        return 2

    items = [
        build_download_item(
            video=v,
            output_base=args.output_path,
            md5=md5,
            errata=errata,
            epic55_base=args.epic55_base_url,
            epic100_base=args.epic100_base_url,
        )
        for v in videos
    ]

    print("EPIC-KITCHENS video downloader with verification")
    print(f"Selected videos: {len(items)}")
    print(f"Output root:     {Path(args.output_path) / 'EPIC-KITCHENS'}")
    print(f"Participants:    {', '.join(sorted(participants)) if participants else 'all'}")
    print(f"Specific videos: {', '.join(sorted(specific_videos)) if specific_videos else 'all'}")
    print(f"Challenges:      {', '.join(challenges) if challenges else 'all'}")
    print(f"Splits:          {', '.join(splits) if splits else 'all'}")
    print(f"SSL verify:      {args.verify_ssl}")

    records = []
    failed = 0
    started = time.monotonic()
    try:
        for i, item in enumerate(items, start=1):
            record = ensure_downloaded(item, args, context, i, len(items))
            records.append(record)
            if record["status"] == "failed":
                failed += 1
    except KeyboardInterrupt:
        if args.report:
            write_report(args.report, records)
        return 130

    elapsed = time.monotonic() - started
    ok_count = sum(1 for r in records if r["status"] in {"ok", "downloaded"})
    downloaded_count = sum(1 for r in records if r["status"] == "downloaded")
    skipped_count = sum(1 for r in records if r["status"] == "ok")

    print("\n" + "=" * 90)
    print("Summary")
    print(f"Complete:    {ok_count}/{len(items)}")
    print(f"Downloaded:  {downloaded_count}")
    print(f"Skipped OK:  {skipped_count}")
    print(f"Failed:      {failed}")
    print(f"Elapsed:     {format_duration(elapsed)}")

    if args.report:
        write_report(args.report, records)

    if failed:
        print("\nFailed videos:")
        for r in records:
            if r["status"] == "failed":
                print(f"  - {r['video_id']}: {r['reason']}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
