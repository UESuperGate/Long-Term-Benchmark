#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(r"C:\Users\xiexi\qingyu")
ANDROID_REPO = ROOT / "_sources" / "element-x-android"
REPORT_DIR = ROOT / "verification_reports"


@dataclass(frozen=True)
class Pair:
    key: str
    task: str
    base_dir: str
    final_dir: str
    base_tag: str
    final_tag: str
    needles: tuple[str, ...]
    snapshot_needles: tuple[str, ...]


PAIRS = (
    Pair(
        key="01_user_status",
        task="User Status",
        base_dir="01_user_status_base_26_07_0",
        final_dir="01_user_status_final_26_08_4",
        base_tag="v26.07.0",
        final_tag="v26.08.4",
        needles=(
            "UserStatusView",
            "UserStatusPresenter",
            "DisplayedUserStatus",
            "DisplayedStatus",
            "setUserStatus",
            "userStatus",
        ),
        snapshot_needles=("UserStatusView",),
    ),
    Pair(
        key="02_gallery_messages",
        task="Gallery Messages",
        base_dir="02_gallery_messages_base_26_06_1",
        final_dir="02_gallery_messages_final_26_08_1",
        base_tag="v26.06.1",
        final_tag="v26.08.1",
        needles=(
            "TimelineItemGalleryView",
            "TimelineItemGalleryContentProvider",
            "galleryContent",
            "GalleryContent",
            "TimelineItemGallery",
        ),
        snapshot_needles=("TimelineItemGalleryView", "TimelineItemGalleryViewScanningContentFailed"),
    ),
    Pair(
        key="03_active_call_timeline",
        task="Active Call Timeline Rendering",
        base_dir="03_active_call_timeline_base_26_07_1",
        final_dir="03_active_call_timeline_final_26_08_0",
        base_tag="v26.07.1",
        final_tag="v26.08.0",
        needles=(
            "ActiveCallTimelineItemView",
            "ActiveCallTimelineItem",
            "ActiveCall",
            "joinCall",
            "renderParticipants",
        ),
        snapshot_needles=("ActiveCallTimelineItemView",),
    ),
    Pair(
        key="04_live_location",
        task="Live Location Sharing",
        base_dir="04_live_location_base_26_04_0",
        final_dir="04_live_location_final_26_05_1",
        base_tag="v26.04.0",
        final_tag="v26.05.1",
        needles=(
            "LiveLocationSharingBanner",
            "ActiveLiveLocationShareManager",
            "LiveLocationShare",
            "toLiveTimelineContent",
            "ShareLocationView",
        ),
        snapshot_needles=("LiveLocationSharingBanner", "ShareLocationView"),
    ),
    Pair(
        key="05_link_new_device",
        task="Link New Device Flow",
        base_dir="05_link_new_device_base_26_05_0",
        final_dir="05_link_new_device_final_26_08_2",
        base_tag="v26.05.0",
        final_tag="v26.08.2",
        needles=(
            "ShowQrCodeView",
            "ShowQrCodePresenter",
            "sendContinuationMessage",
            "hasTimedOut",
            "linknewdevice",
        ),
        snapshot_needles=("ShowQrCodeView",),
    ),
)


SEARCH_PATHS = (
    "features",
    "libraries",
    "services",
    "appnav",
    "appicon",
    "tests/uitests/src/test/kotlin",
)
SNAPSHOT_PATH = "tests/uitests/src/test/snapshots/images"


def run_git(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ANDROID_REPO,
        check=check,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def git_lines(args: list[str], check: bool = True) -> list[str]:
    result = run_git(args, check=check)
    return [line for line in result.stdout.splitlines() if line.strip()]


def collect_grep(tag: str, needles: tuple[str, ...]) -> list[dict]:
    matches: list[dict] = []
    seen: set[tuple[str, int, str]] = set()
    for needle in needles:
        result = run_git(["grep", "-n", "-I", "--break", "-F", needle, tag, "--", *SEARCH_PATHS], check=False)
        if result.returncode not in (0, 1):
            raise RuntimeError(f"git grep failed for {tag} / {needle}: {result.stderr}")
        for line in result.stdout.splitlines():
            parsed = parse_grep_line(tag, line)
            if parsed is None:
                continue
            key = (parsed["path"], parsed["line"], parsed["text"])
            if key in seen:
                continue
            seen.add(key)
            parsed["needle"] = needle
            matches.append(parsed)
    return sorted(matches, key=lambda item: (item["path"], item["line"], item["needle"]))


def parse_grep_line(tag: str, line: str) -> dict | None:
    prefix = f"{tag}:"
    if not line.startswith(prefix):
        return None
    rest = line[len(prefix):]
    path, sep, remainder = rest.partition(":")
    if not sep:
        return None
    line_number, sep, text = remainder.partition(":")
    if not sep or not line_number.isdigit():
        return None
    return {"path": path, "line": int(line_number), "text": text.strip()}


def collect_snapshots(tag: str, needles: tuple[str, ...]) -> list[str]:
    result = run_git(["ls-tree", "-r", "--name-only", tag, SNAPSHOT_PATH], check=False)
    if result.returncode not in (0, 128):
        raise RuntimeError(f"git ls-tree failed for {tag}: {result.stderr}")
    snapshots = []
    for path in result.stdout.splitlines():
        if any(needle in path for needle in needles):
            snapshots.append(path)
    return sorted(snapshots)


def collect_commits(base_tag: str, final_tag: str, needles: tuple[str, ...]) -> list[dict]:
    grep = "--grep=" + "|".join(needles)
    result = run_git(
        ["log", "--oneline", "--decorate=short", "--regexp-ignore-case", "--extended-regexp", grep, f"{base_tag}..{final_tag}"],
        check=False,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError(f"git log failed for {base_tag}..{final_tag}: {result.stderr}")
    commits = []
    for line in result.stdout.splitlines():
        sha, _, subject = line.partition(" ")
        commits.append({"sha": sha, "subject": subject})
    return commits


def collect_path_commits(base_tag: str, final_tag: str, paths: list[str]) -> list[dict]:
    if not paths:
        return []
    result = run_git(["log", "--oneline", "--decorate=short", f"{base_tag}..{final_tag}", "--", *paths[:120]], check=False)
    if result.returncode not in (0, 1):
        raise RuntimeError(f"git log by path failed for {base_tag}..{final_tag}: {result.stderr}")
    commits = []
    for line in result.stdout.splitlines():
        sha, _, subject = line.partition(" ")
        commits.append({"sha": sha, "subject": subject})
    return commits


def collect_changed_paths(base_tag: str, final_tag: str, paths: list[str]) -> list[dict]:
    if not paths:
        return []
    result = run_git(["diff", "--name-status", f"{base_tag}..{final_tag}", "--", *paths[:120]], check=False)
    if result.returncode not in (0, 1):
        raise RuntimeError(f"git diff failed for {base_tag}..{final_tag}: {result.stderr}")
    changes = []
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        changes.append({"status": parts[0], "path": parts[-1]})
    return changes


def summarize_side(tag: str, pair: Pair) -> dict:
    matches = collect_grep(tag, pair.needles)
    snapshots = collect_snapshots(tag, pair.snapshot_needles)
    touched_paths = sorted({item["path"] for item in matches})
    return {
        "tag": tag,
        "sourceMatchCount": len(matches),
        "sourceFiles": touched_paths,
        "sourceMatches": matches[:80],
        "snapshotCount": len(snapshots),
        "snapshots": snapshots,
    }


def classify_delta(base: dict, final: dict) -> str:
    if base["sourceMatchCount"] == 0 and final["sourceMatchCount"] > 0:
        return "introduced_after_base"
    if base["snapshotCount"] == 0 and final["snapshotCount"] > 0:
        return "preview_snapshots_introduced_after_base"
    if final["sourceMatchCount"] > base["sourceMatchCount"]:
        return "expanded_after_base"
    if final["sourceMatchCount"] == base["sourceMatchCount"] and final["snapshotCount"] == base["snapshotCount"]:
        return "present_in_both_tags"
    return "changed_between_tags"


def render_markdown(report: dict) -> str:
    lines = [
        "# Android Tag Target References",
        "",
        "Scope: source, preview snapshot and commit-message evidence for the five Android base/final pairs. This report reads tags directly with `git grep`, `git ls-tree`, and `git log`; it does not change the Android checkout.",
        "",
        "| Pair | Android base | Android final | Delta class | Base refs | Final refs | Base snapshots | Final snapshots | Message commits | Path commits | Changed target paths |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for pair in report["pairs"]:
        lines.append(
            f"| `{pair['key']}` | `{pair['base']['tag']}` | `{pair['final']['tag']}` | `{pair['deltaClass']}` | "
            f"{pair['base']['sourceMatchCount']} | {pair['final']['sourceMatchCount']} | "
            f"{pair['base']['snapshotCount']} | {pair['final']['snapshotCount']} | "
            f"{len(pair['messageCommits'])} | {len(pair['pathCommits'])} | {len(pair['changedPaths'])} |"
        )
    lines.append("")
    lines.append("## Pair Details")
    for pair in report["pairs"]:
        lines.extend([
            "",
            f"### {pair['key']} - {pair['task']}",
            "",
            f"- Base ArkTS dir: `{pair['baseDir']}`",
            f"- Final ArkTS dir: `{pair['finalDir']}`",
            f"- Delta class: `{pair['deltaClass']}`",
            f"- Base Android source files: {format_paths(pair['base']['sourceFiles'])}",
            f"- Final Android source files: {format_paths(pair['final']['sourceFiles'])}",
            f"- Base Android snapshots: {pair['base']['snapshotCount']}",
            f"- Final Android snapshots: {pair['final']['snapshotCount']}",
            f"- Changed target paths: {format_change_paths(pair['changedPaths'])}",
        ])
        if pair["commits"]:
            lines.append("- Relevant commits:")
            for commit in pair["commits"][:12]:
                lines.append(f"  - `{commit['sha']}` {commit['subject']}")
        else:
            lines.append("- Relevant commits: none found by target-name or target-path grep.")
        final_examples = pair["final"]["sourceMatches"][:8]
        if final_examples:
            lines.append("- Final source anchors:")
            for item in final_examples:
                text = item["text"].replace("|", "\\|")
                lines.append(f"  - `{item['path']}:{item['line']}` `{item['needle']}` {text}")
    return "\n".join(lines) + "\n"


def format_paths(paths: list[str]) -> str:
    if not paths:
        return "none"
    return ", ".join(f"`{path}`" for path in paths[:8]) + (" ..." if len(paths) > 8 else "")


def format_change_paths(changes: list[dict]) -> str:
    if not changes:
        return "none"
    return ", ".join(f"`{item['status']} {item['path']}`" for item in changes[:8]) + (" ..." if len(changes) > 8 else "")


def merge_commits(*commit_lists: list[dict]) -> list[dict]:
    merged = []
    seen = set()
    for commits in commit_lists:
        for commit in commits:
            sha = commit["sha"]
            if sha in seen:
                continue
            seen.add(sha)
            merged.append(commit)
    return merged


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    pairs = []
    for pair in PAIRS:
        base = summarize_side(pair.base_tag, pair)
        final = summarize_side(pair.final_tag, pair)
        target_paths = sorted(set(base["sourceFiles"]) | set(final["sourceFiles"]) | set(base["snapshots"]) | set(final["snapshots"]))
        message_commits = collect_commits(pair.base_tag, pair.final_tag, pair.needles)
        path_commits = collect_path_commits(pair.base_tag, pair.final_tag, target_paths)
        pair_report = {
            "key": pair.key,
            "task": pair.task,
            "baseDir": pair.base_dir,
            "finalDir": pair.final_dir,
            "base": base,
            "final": final,
            "messageCommits": message_commits,
            "pathCommits": path_commits,
            "commits": merge_commits(message_commits, path_commits),
            "changedPaths": collect_changed_paths(pair.base_tag, pair.final_tag, target_paths),
            "deltaClass": classify_delta(base, final),
        }
        pairs.append(pair_report)

    report = {
        "androidRepo": str(ANDROID_REPO),
        "searchPaths": list(SEARCH_PATHS),
        "snapshotPath": SNAPSHOT_PATH,
        "pairs": pairs,
    }
    json_path = REPORT_DIR / "android_tag_target_references.json"
    md_path = REPORT_DIR / "android_tag_target_references.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    md_path.write_text(render_markdown(report), encoding="utf-8", newline="\n")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    for pair in pairs:
        print(
            f"{pair['key']}\t{pair['deltaClass']}\t"
            f"base refs={pair['base']['sourceMatchCount']} snapshots={pair['base']['snapshotCount']}\t"
            f"final refs={pair['final']['sourceMatchCount']} snapshots={pair['final']['snapshotCount']}\t"
            f"commits={len(pair['commits'])}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
