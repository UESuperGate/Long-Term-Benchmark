#!/usr/bin/env python3
"""Evaluate extended Element X tasks against shared transition contracts.

The observer is evaluator-owned and only reads production sources. A case passes
when every state/event/effect clause has evidence in the implementation. Rules
use implementation-tolerant alternatives for Android Kotlin and ArkTS, while
case IDs and digests always come from the shared platform-neutral contract.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ANDROID_REPO = ROOT / "_sources/element-x-android"
TASKS = {
    "06_multi_select_polls": {
        "contract": ROOT / "benchmark_tasks/06_multi_select_polls/transitions.json",
        "androidRoots": ("features/poll/", "features/messages/"),
        "baseTag": "v26.08.4",
        "finalTag": "v26.09.1",
        "arktsBase": ROOT / "06_multi_select_polls_base_26_08_4",
        "arktsFinal": ROOT / "final_dev_nodes/06_multi_select_polls_final_26_09_1",
    },
    "07_recent_search_history": {
        "contract": ROOT / "benchmark_tasks/07_recent_search_history/transitions.json",
        "androidRoots": ("features/home/", "libraries/matrix/"),
        "baseTag": "v26.09.2",
        "finalTag": "v26.09.3",
        "arktsBase": ROOT / "07_recent_search_history_base_26_09_2",
        "arktsFinal": ROOT / "final_dev_nodes/07_recent_search_history_final_26_09_3",
    },
}


def option(path: str, *patterns: str, forbid: tuple[str, ...] = ()) -> dict[str, Any]:
    return {"path": path, "patterns": patterns, "forbid": forbid}


def clause(*options: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    return options


# Each tuple is an AND clause; options inside a clause are OR alternatives.
ANDROID_RULES: dict[str, tuple[tuple[dict[str, Any], ...], ...]] = {
    "mp_state_001_default_limit": (
        clause(
            option(r"CreatePollState\.kt$", r"val maxSelections: Int", r"val maxAllowedSelections: Int"),
            option(r"PollFormState\.kt$", r"val maxSelections: Int = MIN_SELECTIONS", r"val effectiveMaxSelections", r"coerceIn\(MIN_SELECTIONS"),
        ),
        clause(
            option(r"CreatePollPresenter\.kt$", r"maxSelections = poll\.maxSelections", r"maxAllowedSelections = poll\.answers\.size"),
            option(r"CreatePollPresenter\.kt$", r"val maxSelections: Int", r"poll\.effectiveMaxSelections", r"maxOf\(poll\.answers\.size, MIN_SELECTIONS\)"),
        ),
        clause(
            option(r"CreatePollView\.kt$", r"maxAllowedSelections", r"SetMaxSelections"),
            option(r"CreatePollView\.kt$", r"MaxSelectionsRow", r"CreatePollEvent\.SetMaxSelections\(state\.maxSelections"),
        ),
    ),
    "mp_state_002_set_limit": (
        clause(
            option(r"CreatePollEvent\.kt$", r"SetMaxSelections\(val maxSelections: Int\)"),
            option(r"CreatePollEvent\.kt$", r"SetMaxSelections\(val value: Int\)"),
        ),
        clause(
            option(r"CreatePollPresenter\.kt$", r"CreatePollEvent\.SetMaxSelections", r"poll\.copy\(maxSelections = event\.maxSelections\)"),
            option(r"CreatePollPresenter\.kt$", r"CreatePollEvent\.SetMaxSelections", r"poll = poll\.withMaxSelections\(event\.value\)"),
        ),
    ),
    "mp_state_003_remove_clamps_limit": (
        clause(
            option(r"PollFormState\.kt$", r"fun withAnswerRemoved", r"val newAnswers", r"maxSelections\.coerceIn\(1, newAnswers\.size\)"),
            option(r"PollFormState\.kt$", r"fun withAnswerRemoved", r"val newAnswers", r"maxSelections\.coerceIn\(MIN_SELECTIONS, maxOf\(newAnswers\.size, MIN_SELECTIONS\)\)", r"maxSelections = clampedMaxSelections"),
        ),
    ),
    "mp_state_004_edit_restores_limit": (
        clause(option(r"CreatePollPresenter\.kt$", r"mode is CreatePollMode\.EditPoll", r"repository\.getPoll", r"maxSelections = it\.maxSelections\.toInt\(\)")),
    ),
    "mp_state_005_save_sends_limit": (
        clause(
            option(r"CreatePollPresenter\.kt$", r"repository\.savePoll", r"answers = poll\.answers", r"maxSelections = poll\.maxSelections"),
            option(r"CreatePollPresenter\.kt$", r"repository\.savePoll", r"answers = poll\.answers", r"maxSelections = poll\.effectiveMaxSelections"),
        ),
        clause(option(r"CreatePollPresenter\.kt$", r"\.onSuccess", r"capturePollSaved", r"\.onFailure", r"trackSavePollFailed")),
    ),
    "mp_state_006_submit_multiple_answers": (
        clause(option(r"SendPollResponseAction\.kt$", r"answerIds: List<String>")),
        clause(option(r"DefaultSendPollResponseAction\.kt$", r"answers = answerIds")),
        clause(
            option(r"PollContentView\.kt$", r"newSelections", r"onSendPollResponse\(it, newSelections\)"),
            option(r"TimelinePresenter\.kt$", r"submitPendingPollAnswers", r"sendPollResponseAction\.execute", r"answerIds = pending\.selectedAnswerIds"),
        ),
    ),
    "mp_state_007_limit_disables_unselected": (
        clause(
            option(r"DefaultPollContentStateFactory\.kt$", r"isSelectionLimitReached", r"!isSelectionLimitReached \|\| isSelected", r"!isPollEnded"),
            option(r"DefaultPollContentStateFactory\.kt$", r"val selectedCount = selectedAnswerIds\.size", r"val isEnabled = !isPollEnded", r"isSelected \|\| selectedCount < maxSelections"),
        ),
    ),
    "mp_state_008_deselect_reopens_choices": (
        clause(
            option(r"PollContentView\.kt$", r"item\.copy\(isSelected = !item\.isSelected\)", r"filter \{ it\.isSelected \}", r"newSelections\.size <= maxSelections\.toInt\(\)"),
            option(r"TimelinePresenter\.kt$", r"overlayPendingPollSelection", r"val selectedCount = selectedIds\.size", r"isSelected \|\| selectedCount < maxSelections", r"answerItem\.copy\(isSelected = isSelected, isEnabled = isEnabled\)"),
        ),
        clause(
            option(r"DefaultPollContentStateFactory\.kt$", r"currentSelectionCount", r"isSelectionLimitReached", r"isSelected"),
            option(r"TimelinePresenter\.kt$", r"togglePendingPollAnswer", r"answerId in seedSelection -> seedSelection - answerId", r"seedSelection\.size < maxSelections -> seedSelection \+ answerId"),
        ),
    ),
    "mp_state_009_failure_keeps_selection": (
        clause(option(r"DefaultSendPollResponseAction\.kt$", r"answerIds: List<String>", r": Result<Unit>", r"\.onSuccess", r"analyticsService\.capture")),
        clause(option(r"DefaultPollContentStateFactory\.kt$", r"val myVotes", r"val isSelected = answer\.id in myVotes")),
    ),
    "rs_state_001_empty_history": (
        clause(
            option(r"DefaultSearchHistoryStore\.kt$", r"MutableStateFlow<List<SearchHistoryResult>>\(emptyList\(\)\)", r"ensureLoaded", r"emitAll\(cache\)"),
            option(r"DefaultRecentSearchHistoryStore\.kt$", r"fun history\(\): Flow<ImmutableList<RecentSearchHistoryEntry>>", r"emptyList<RecentSearchHistoryEntry>", r"decodeEntries"),
        ),
        clause(
            option(r"GlobalSearchPresenter\.kt$", r"produceState<AsyncData<ImmutableList<SearchHistoryResultItem>>>", r"AsyncData\.Success"),
            option(r"GlobalSearchPresenter\.kt$", r"recentSearchHistoryStore\.history\(\)\.collectAsState", r"initialValue = AsyncData\.Loading", r"mapRecentHistoryForUi", r"AsyncData\.Success"),
        ),
    ),
    "rs_state_002_save_query": (
        clause(
            option(r"GlobalSearchPresenter\.kt$", r"GlobalSearchEvent\.SaveQueryToHistory", r"term\.isNotBlank\(\)", r"searchHistoryStore\.add\(SearchHistoryResult\.Query\(term\)\)"),
            option(r"GlobalSearchPresenter\.kt$", r"GlobalSearchEvent\.SubmitQuery", r"recentSearchHistoryStore\.saveQuery\(current\)"),
        ),
    ),
    "rs_state_003_ignore_blank_query": (
        clause(
            option(r"GlobalSearchPresenter\.kt$", r"SaveQueryToHistory", r"if \(term\.isNotBlank\(\)\)", r"searchHistoryStore\.add"),
            option(r"DefaultRecentSearchHistoryStore\.kt$", r"suspend fun saveQuery\(term: String\)", r"val trimmed = term\.trim\(\)", r"if \(trimmed\.isEmpty\(\)\) return"),
        ),
    ),
    "rs_state_004_save_room": (
        clause(
            option(r"GlobalSearchPresenter\.kt$", r"SaveRoomToHistory", r"searchHistoryStore\.add\(SearchHistoryResult\.Room\(event\.roomId\)\)"),
            option(r"GlobalSearchPresenter\.kt$", r"GlobalSearchEvent\.SaveRoom", r"recentSearchHistoryStore\.saveRoom\(event\.roomId\)"),
        ),
        clause(
            option(r"SearchHistoryResult\.kt$", r"data class Room", r"roomId: RoomId"),
            option(r"RecentSearchHistoryEntry\.kt$", r"data class Room\(val roomId: RoomId\)", r"TYPE_ROOM"),
        ),
    ),
    "rs_state_005_duplicate_moves_front": (
        clause(
            option(r"DefaultSearchHistoryStore\.kt$", r"add\(result\)", r"filterNot \{ it == result \}", r"\.distinct\(\)"),
            option(r"DefaultRecentSearchHistoryStore\.kt$", r"fun addToFront", r"filterNot \{ it\.typeTag == entry\.typeTag && it\.key == entry\.key \}", r"listOf\(entry\) \+ withoutDuplicate"),
        ),
    ),
    "rs_state_006_capacity_drops_oldest": (
        clause(
            option(r"SearchHistoryStore\.kt$|DefaultSearchHistoryStore\.kt$", r"MAX_SEARCH_HISTORY_SIZE\s*=\s*25"),
            option(r"RecentSearchHistoryStore\.kt$", r"MAX_HISTORY_SIZE: Int = 25"),
        ),
        clause(
            option(r"DefaultSearchHistoryStore\.kt$", r"add\(result\)", r"\.take\(MAX_SEARCH_HISTORY_SIZE\)"),
            option(r"DefaultRecentSearchHistoryStore\.kt$", r"withNew\.size > RecentSearchHistoryStore\.MAX_HISTORY_SIZE", r"withNew\.take\(RecentSearchHistoryStore\.MAX_HISTORY_SIZE\)"),
        ),
    ),
    "rs_state_007_persisted_roundtrip": (
        clause(
            option(r"DefaultSearchHistoryStore\.kt$", r"json\.decodeFromString", r"json\.encodeToString", r"fileStore\.write"),
            option(r"DefaultRecentSearchHistoryStore\.kt$", r"json\.encodeToString", r"json\.parseToJsonElement", r"store\.edit \{ prefs -> prefs\[historyKey\] = encoded \}"),
        ),
        clause(
            option(r"SearchHistoryResult\.kt$", r"Serializable", r"data class Query", r"data class Room"),
            option(r"RecentSearchHistoryEntry\.kt$", r"sealed interface RecentSearchHistoryEntry", r"data class Query", r"data class Room"),
        ),
    ),
    "rs_state_008_clear_history": (
        clause(
            option(r"DefaultSearchHistoryStore\.kt$", r"override suspend fun clear", r"cache\.value = emptyList\(\)", r"fileStore\.delete\(\)"),
            option(r"DefaultRecentSearchHistoryStore\.kt$", r"override suspend fun clear\(\)", r"store\.edit \{ prefs -> prefs\.remove\(historyKey\) \}"),
        ),
    ),
    "rs_state_009_corruption_recovers": (
        clause(
            option(r"DefaultSearchHistoryStore\.kt$", r"runCatchingExceptions", r"getOrElse", r"emptyList\(\)", r"persist\(updated\)"),
            option(r"DefaultRecentSearchHistoryStore\.kt$", r"decodeEntries", r"runCatching", r"getOrElse", r"return emptyList<RecentSearchHistoryEntry>", r"persist\(updated\)"),
        ),
    ),
    "rs_state_010_select_query_restarts_search": (
        clause(
            option(r"GlobalSearchPresenter\.kt$", r"SearchHistoryResultSelected", r"replace\(0, length, event\.resultItem\.term\)", r"searchResults = AsyncData\.Loading\(\)", r"currentTarget = GlobalSearchTarget\.ROOMS"),
            option(r"GlobalSearchPresenter\.kt$", r"onSelectRecentEntry", r"setTextAndPlaceCursorAtEnd\(entry\.term\)", r"setCurrentTarget\(GlobalSearchTarget\.ROOMS\)", r"LaunchedEffect\(queryState\.text\)", r"AsyncData\.Loading"),
        ),
    ),
    "rs_state_011_missing_room_filtered": (
        clause(
            option(r"GlobalSearchPresenter\.kt$", r"history\.mapNotNull", r"matrixClient\.getRoomInfo\(result\.roomId\)\.getOrNull\(\)", r"return@mapNotNull null", r"AsyncData\.Success"),
            option(r"GlobalSearchPresenter\.kt$", r"mapRecentHistoryForUi", r"getRoomInfoFlow\(entry\.roomId\)\.first\(\)\.getOrNull\(\)", r"if \(roomInfo != null\)", r"\.filterNotNull\(\)", r"AsyncData\.Success"),
        ),
    ),
}


ARKTS_RULES: dict[str, tuple[tuple[dict[str, Any], ...], ...]] = {
    "mp_state_001_default_limit": (
        clause(
            option(r"PollFeature\.ets$", r"maxSelections: number = 1", r"get maxAllowedSelections", r"return this\.draft\.answers\.length"),
            option(r"PollFeature\.ets$", r"maxSelections: number = 1", r"validAnswerCount", r"effectiveMaxSelections"),
        ),
        clause(option(r"Index\.ets$", r"Max(?:imum)? selections", r"poll_max_selections(?:_input)?|setMaxSelections")),
    ),
    "mp_state_002_set_limit": (
        clause(
            option(r"PollFeature\.ets$", r"setMaxSelections\(maxSelections: number\)", r"this\.clampMaxSelections\(maxSelections\)"),
            option(r"PollFeature\.ets$", r"setMaxSelections\(value: number\)", r"Math\.floor\(value\)", r"validAnswerCount", r"draft\.maxSelections"),
        ),
    ),
    "mp_state_003_remove_clamps_limit": (
        clause(
            option(r"PollFeature\.ets$", r"removeAnswer\(index: number\)", r"answers\.splice\(index, 1\)", r"maxSelections = this\.clampMaxSelections"),
            option(r"PollFeature\.ets$", r"removeAnswer\(index: number\)", r"answers\.splice\(index, 1\)", r"maxSelections > newCount", r"maxSelections = newCount", r"maxSelections < 1"),
        ),
    ),
    "mp_state_004_edit_restores_limit": (
        clause(
            option(r"PollFeature\.ets$", r"loadExisting\(", r"answers\.map", r"maxSelections = this\.clampMaxSelections\(maxSelections\)"),
            option(r"PollFeature\.ets$", r"restoreFrom\(stored: PollDraft\)", r"stored\.answers\.map", r"stored\.kind", r"stored\.maxSelections", r"draft\.maxSelections = restoredMax"),
        ),
    ),
    "mp_state_005_save_sends_limit": (
        clause(option(r"PollFeature\.ets$", r"createPoll\(question: string, answers: string\[\], maxSelections: number\)", r"lastCreatedMaxSelections = maxSelections")),
        clause(option(r"PollFeature\.ets$", r"this\.gateway\.createPoll", r"this\.draft\.maxSelections", r"PollSubmissionState\.Success", r"PollSubmissionState\.Failure")),
    ),
    "mp_state_006_submit_multiple_answers": (
        clause(option(r"PollFeature\.ets$", r"sendPollResponse\(answerIds: string\[\]\)", r"lastResponseAnswerIds = answerIds\.slice\(\)")),
        clause(
            option(r"PollFeature\.ets$", r"submitVote\(\)", r"sendPollResponse\(this\.selectedAnswerIds\)"),
            option(r"PollFeature\.ets$", r"submitVote\(\)", r"orderedIds = this\.selectedAnswerIds\.slice\(\)", r"sendPollResponse\(orderedIds\)"),
        ),
    ),
    "mp_state_007_limit_disables_unselected": (
        clause(
            option(r"PollFeature\.ets$", r"isAnswerEnabled\(answerId: string, ended: boolean\)", r"selectedAnswerIds\.length >= this\.draft\.maxSelections", r"!limitReached \|\| this\.selectedAnswerIds\.includes\(answerId\)"),
            option(r"PollFeature\.ets$", r"isAnswerEnabled\(answerId: string, ended: boolean\)", r"if \(ended\)", r"isSelected", r"selectedAnswerIds\.length < this\.draft\.effectiveMaxSelections\(\)"),
        ),
    ),
    "mp_state_008_deselect_reopens_choices": (
        clause(
            option(r"PollFeature\.ets$", r"toggleAnswer\(answerId: string\)", r"filter\(\(selected: string\) => selected !== answerId\)", r"selectedAnswerIds\.length < this\.draft\.maxSelections", r"concat\(answerId\)"),
            option(r"PollFeature\.ets$", r"toggleAnswer\(answerId: string\)", r"indexOf\(answerId\)", r"splice\(idx, 1\)", r"selectedAnswerIds\.length >= limit", r"selectedAnswerIds\.push\(answerId\)"),
        ),
    ),
    "mp_state_009_failure_keeps_selection": (
        clause(
            option(r"PollFeature\.ets$", r"submitVote\(\)", r"PollSubmissionState\.Loading", r"sendPollResponse\(this\.selectedAnswerIds\)", r"succeeded \? PollSubmissionState\.Success : PollSubmissionState\.Failure"),
            option(r"PollFeature\.ets$", r"submitVote\(\)", r"orderedIds = this\.selectedAnswerIds\.slice\(\)", r"sendPollResponse\(orderedIds\)", r"PollSubmissionState\.Failure"),
        ),
    ),
    "rs_state_001_empty_history": (
        clause(
            option(r"SearchHistory\.ets$", r"cache: SearchHistoryResult\[\] = \[\]", r"async load", r"readFromDisk"),
            option(r"RecentSearchHistoryStore\.ets$", r"async load\(\): Promise<RecentSearchEntry\[\]>", r"return \[\]", r"parseEntries"),
        ),
        clause(
            option(r"GlobalSearchFeature\.ets$", r"openSearch", r"this\.history =", r"historyLoaded = true"),
            option(r"GlobalSearchFeature\.ets$", r"recentHistoryState", r"async loadHistory", r"RecentHistoryState\.Loading", r"RecentHistoryState\.Empty"),
        ),
    ),
    "rs_state_002_save_query": (
        clause(
            option(r"GlobalSearchFeature\.ets$", r"saveQueryToHistory", r"const term = this\.query\.trim\(\)", r"SearchHistoryResult\.query\(term\)"),
            option(r"GlobalSearchFeature\.ets$", r"saveQueryToHistory\(query: string\)", r"query\.trim\(\)", r"addEntry\(createQueryEntry\(trimmed\)\)"),
        ),
    ),
    "rs_state_003_ignore_blank_query": (
        clause(
            option(r"GlobalSearchFeature\.ets$", r"saveQueryToHistory", r"if \(term\.length === 0\)", r"return;"),
            option(r"GlobalSearchFeature\.ets$", r"saveQueryToHistory", r"if \(trimmed\.length === 0\)", r"return false"),
        ),
    ),
    "rs_state_004_save_room": (
        clause(
            option(r"GlobalSearchFeature\.ets$", r"saveRoomToHistory", r"SearchHistoryResult\.room\(roomId\)"),
            option(r"GlobalSearchFeature\.ets$", r"saveRoomToHistory\(roomId: string\)", r"addEntry\(createRoomEntry\(trimmed\)\)"),
        ),
        clause(
            option(r"SearchHistory\.ets$", r"static room\(roomId: string\)", r"SearchHistoryResultType\.Room"),
            option(r"RecentSearchHistory\.ets$", r"createRoomEntry\(roomId: string\)", r"RecentSearchEntryType\.Room"),
        ),
    ),
    "rs_state_005_duplicate_moves_front": (
        clause(
            option(r"SearchHistory\.ets$", r"const updated: SearchHistoryResult\[\] = \[result\]", r"item\.id !== result\.id", r"updated\.push\(item\)"),
            option(r"GlobalSearchFeature\.ets$", r"async addEntry", r"entriesEqual\(existing, entry\)", r"filtered\.unshift\(entry\)"),
        ),
    ),
    "rs_state_006_capacity_drops_oldest": (
        clause(
            option(r"SearchHistory\.ets$", r"MAX_SEARCH_HISTORY_SIZE: number = 25", r"updated\.length < MAX_SEARCH_HISTORY_SIZE"),
            option(r"RecentSearchHistoryStore\.ets$", r"RECENT_HISTORY_CAPACITY: number = 25"),
        ),
        clause(option(r"GlobalSearchFeature\.ets$", r"filtered\.length > RECENT_HISTORY_CAPACITY", r"filtered\.length = RECENT_HISTORY_CAPACITY"), option(r"SearchHistory\.ets$", r"updated\.length < MAX_SEARCH_HISTORY_SIZE")),
    ),
    "rs_state_007_persisted_roundtrip": (
        clause(
            option(r"SearchHistory\.ets$", r"JSON\.parse", r"JSON\.stringify", r"store\.put", r"store\.flush"),
            option(r"RecentSearchHistoryStore\.ets$", r"fs\.readText", r"JSON\.parse", r"JSON\.stringify", r"fs\.writeSync"),
        ),
        clause(
            option(r"SearchHistory\.ets$", r"SearchHistoryResultType\.Query", r"SearchHistoryResultType\.Room"),
            option(r"RecentSearchHistory\.ets$", r"RecentSearchEntryType\.Query", r"RecentSearchEntryType\.Room", r"serializeEntry", r"deserializeEntry"),
        ),
        clause(
            option(r"Index\.ets$", r"new SearchHistoryStore\(\)", forbid=(r"InMemoryRecentSearchHistoryStore",)),
            option(r"Index\.ets$", r"new FileRecentSearchHistoryStore\(", forbid=(r"new InMemoryRecentSearchHistoryStore\(\)",)),
        ),
    ),
    "rs_state_008_clear_history": (
        clause(
            option(r"SearchHistory\.ets$", r"async clear", r"this\.cache = \[\]", r"store\.delete", r"store\.flush"),
            option(r"RecentSearchHistoryStore\.ets$", r"clear\(\): Promise<void>", r"fs\.unlink"),
        ),
        clause(
            option(r"GlobalSearchFeature\.ets$", r"clearHistory", r"this\.store\.clear", r"this\.history = \[\]"),
            option(r"GlobalSearchFeature\.ets$", r"clearHistory", r"this\.recentHistory = \[\]", r"this\.store\.clear"),
        ),
    ),
    "rs_state_009_corruption_recovers": (
        clause(
            option(r"SearchHistory\.ets$", r"try \{", r"JSON\.parse", r"catch \(error\)", r"return \[\]", r"await this\.persist\(context\)"),
            option(r"RecentSearchHistoryStore\.ets$", r"parseEntries", r"JSON\.parse", r"catch \(err\)", r"return \[\]"),
        ),
        clause(option(r"GlobalSearchFeature\.ets$", r"async addEntry", r"await this\.store\.save\(this\.recentHistory\)"), option(r"SearchHistory\.ets$", r"async add", r"await this\.persist\(context\)")),
    ),
    "rs_state_010_select_query_restarts_search": (
        clause(
            option(r"GlobalSearchFeature\.ets$", r"selectHistoryResult", r"this\.query = result\.value", r"GlobalSearchTarget\.Rooms", r"SearchResultState\.Loading"),
            option(r"GlobalSearchFeature\.ets$", r"selectHistoryEntry", r"this\.query = entry\.term", r"this\.target = GlobalSearchTarget\.Rooms", r"SearchResultState\.Loading"),
        ),
    ),
    "rs_state_011_missing_room_filtered": (
        clause(
            option(r"GlobalSearchFeature\.ets$", r"stored\.filter", r"SearchHistoryResultType\.Query \|\| accessibleRoomIds\.includes\(item\.value\)", r"historyLoaded = true"),
            option(r"GlobalSearchFeature\.ets$", r"mapHistoryForUi", r"resolveRoomInfos", r"accessibleById\.get\(entry\.term\)", r"if \(info === undefined\)", r"continue"),
        ),
    ),
}


def strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"//.*", "", text)


def android_tag_sources(repo: Path, tag: str, roots: tuple[str, ...]) -> dict[str, str]:
    names = subprocess.check_output(["git", "-C", str(repo), "ls-tree", "-r", "--name-only", tag], text=True).splitlines()
    result: dict[str, str] = {}
    for name in names:
        if not name.endswith(".kt") or "/src/main/" not in f"/{name}" or not name.startswith(roots):
            continue
        source = subprocess.check_output(["git", "-C", str(repo), "show", f"{tag}:{name}"], text=True, errors="replace")
        result[name] = strip_comments(source)
    return result


def directory_sources(root: Path, suffix: str, roots: tuple[str, ...] | None = None) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in root.rglob(f"*{suffix}"):
        relative = path.relative_to(root).as_posix()
        if any(part in {"build", ".gradle", ".hvigor", "oh_modules", "node_modules", "test", "tests"} for part in path.parts):
            continue
        if roots and ("/src/main/" not in f"/{relative}" or not relative.startswith(roots)):
            continue
        if not roots and "/src/main/" not in f"/{relative}":
            continue
        result[relative] = strip_comments(path.read_text(encoding="utf-8", errors="replace"))
    return result


def match_option(rule: dict[str, Any], sources: dict[str, str]) -> tuple[bool, str | None]:
    path_re = re.compile(rule["path"])
    patterns = [re.compile(pattern, re.IGNORECASE | re.DOTALL) for pattern in rule["patterns"]]
    forbids = [re.compile(pattern, re.IGNORECASE | re.DOTALL) for pattern in rule["forbid"]]
    for path, source in sources.items():
        if path_re.search(path) and all(pattern.search(source) for pattern in patterns) and not any(pattern.search(source) for pattern in forbids):
            return True, path
    return False, None


def score_case(case: dict[str, Any], rules: dict[str, Any], sources: dict[str, str]) -> dict[str, Any]:
    evidence = []
    for index, alternatives in enumerate(rules[case["caseId"]], start=1):
        matched_path = None
        for candidate in alternatives:
            matched, path = match_option(candidate, sources)
            if matched:
                matched_path = path
                break
        evidence.append({"clause": index, "passed": matched_path is not None, "path": matched_path})
    passed = all(item["passed"] for item in evidence)
    return {
        "caseId": case["caseId"],
        "taskId": case["taskId"],
        "traceDigest": case["traceDigest"],
        "semanticStatus": "passed" if passed else "failed",
        "evidenceSource": "production_state_event_effect_structure",
        "clauses": evidence,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=TASKS, required=True)
    parser.add_argument("--platform", choices=("android", "arkts"), required=True)
    parser.add_argument("--role", choices=("base", "final", "agent"), required=True)
    parser.add_argument("--source-root", type=Path, help="Required for agent role; optional override for base/final.")
    parser.add_argument("--source-repo", type=Path, default=ANDROID_REPO)
    parser.add_argument("--code-generated", choices=("passed", "failed"), default="passed")
    parser.add_argument("--compile", dest="compile_status", choices=("passed", "failed", "not_run"), default="passed")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    task = TASKS[args.task]
    contract = json.loads(task["contract"].read_text(encoding="utf-8"))
    rules = ANDROID_RULES if args.platform == "android" else ARKTS_RULES
    case_ids = {case["caseId"] for case in contract["cases"]}
    missing = case_ids - set(rules)
    if missing:
        raise RuntimeError(f"Missing observer rules: {sorted(missing)}")

    if args.platform == "android" and args.role in {"base", "final"} and not args.source_root:
        tag = task[f"{args.role}Tag"]
        sources = android_tag_sources(args.source_repo, tag, task["androidRoots"])
        source_identity = tag
    else:
        source_root = args.source_root or task[f"arkts{args.role.title()}"]
        if not source_root.exists():
            raise FileNotFoundError(source_root)
        suffix = ".kt" if args.platform == "android" else ".ets"
        roots = task["androidRoots"] if args.platform == "android" else None
        sources = directory_sources(source_root, suffix, roots)
        source_identity = str(source_root.resolve())

    rows = [score_case(case, rules, sources) for case in contract["cases"]]
    counts = Counter(row["semanticStatus"] for row in rows)
    payload = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "taskId": args.task,
        "platform": args.platform,
        "role": args.role,
        "sourceIdentity": source_identity,
        "contract": str(task["contract"].relative_to(ROOT)),
        "codeGeneration": args.code_generated,
        "compile": args.compile_status,
        "semantic": {
            "passed": counts["passed"],
            "failed": counts["failed"],
            "total": len(rows),
            "cases": rows,
        },
        "diagnostics": {
            "observerOwner": "evaluator",
            "observationMode": "production_state_event_effect_structure",
            "sourceFileCount": len(sources),
            "notScored": 0,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"task": args.task, "platform": args.platform, "role": args.role, "sources": len(sources), "passed": counts["passed"], "failed": counts["failed"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
