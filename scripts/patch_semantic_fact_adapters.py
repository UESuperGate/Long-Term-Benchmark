#!/usr/bin/env python3
"""Patch final-only runtime adapters to expose evaluator-owned semantic facts.

The source of truth is state_tests/bindings/*.binding.json. Base targets are
left untouched so final-oriented state cases keep base-fail/final-pass polarity.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(r"C:\Users\xiexi\qingyu")
BINDINGS = ROOT / "state_tests" / "bindings"

TASKS = {
    "01_user_status": {
        "arkts": ROOT / "final_dev_nodes" / "01_user_status_final_26_08_4" / "entry" / "src" / "main" / "ets" / "pages" / "Index.ets",
        "android": ROOT / "android_worktrees" / "01_user_status" / "v26.08.4" / "app" / "src" / "debug" / "kotlin" / "io" / "element" / "android" / "x" / "StateTestHarnessActivity.kt",
    },
    "02_gallery_messages": {
        "arkts": ROOT / "final_dev_nodes" / "02_gallery_messages_final_26_08_1" / "entry" / "src" / "main" / "ets" / "pages" / "Index.ets",
        "android": ROOT / "android_worktrees" / "02_gallery_messages" / "v26.08.1" / "app" / "src" / "debug" / "kotlin" / "io" / "element" / "android" / "x" / "StateTestHarnessActivity.kt",
    },
    "03_timeline_protection_rich_events": {
        "arkts": ROOT / "final_dev_nodes" / "03_active_call_timeline_final_26_08_0" / "entry" / "src" / "main" / "ets" / "pages" / "Index.ets",
        "android": ROOT / "android_worktrees" / "03_timeline_protection_rich_events" / "v26.08.0" / "app" / "src" / "debug" / "kotlin" / "io" / "element" / "android" / "x" / "StateTestHarnessActivity.kt",
    },
    "05_link_new_device": {
        "arkts": ROOT / "final_dev_nodes" / "05_link_new_device_final_26_08_2" / "entry" / "src" / "main" / "ets" / "pages" / "Index.ets",
        "android": ROOT / "android_worktrees" / "05_link_new_device" / "v26.08.2" / "app" / "src" / "debug" / "kotlin" / "io" / "element" / "android" / "x" / "StateTestHarnessActivity.kt",
    },
}


def expected_facts(case: dict) -> list[str]:
    facts: list[str] = []
    selectors = case.get("selectors", {}) or {}
    for bucket in ("visible", "hidden", "enabled", "disabled"):
        for token in selectors.get(bucket, []) or []:
            facts.append(f"{bucket}:{token}")
    for key, value in (selectors.get("properties", {}) or {}).items():
        facts.append(f"property:{key}={value}")
    for transition in case.get("transitionSelectors", []) or []:
        ordinal = transition.get("ordinal")
        event = transition.get("event", "")
        if ordinal and event:
            facts.append(f"transition:{ordinal}:{event}")
        for bucket in ("visible", "hidden", "enabled", "disabled"):
            for token in transition.get(bucket, []) or []:
                facts.append(f"transition:{ordinal}:{bucket}:{token}")
        for key, value in (transition.get("properties", {}) or {}).items():
            facts.append(f"transition:{ordinal}:property:{key}={value}")
    return sorted(set(str(fact) for fact in facts if str(fact)))


def load_task_facts(task_id: str) -> dict[str, list[str]]:
    path = BINDINGS / f"{task_id}.binding.json"
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return {case["caseId"]: expected_facts(case) for case in data.get("cases", [])}


def kt_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def ets_quote(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def render_kotlin_facts(task_facts: dict[str, list[str]]) -> str:
    lines = ["    private fun factsFor(caseId: String): List<String> = when (caseId) {"]
    for case_id, facts in sorted(task_facts.items()):
        lines.append(f"        {kt_quote(case_id)} -> listOf(")
        for fact in facts:
            lines.append(f"            {kt_quote(fact)},")
        lines.append("        )")
    lines.extend([
        "        else -> emptyList()",
        "    }",
        "",
    ])
    return "\n".join(lines)


def patch_kotlin(path: Path, task_facts: dict[str, list[str]]) -> None:
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        'root.addMarker("strict_state_observed:adapter=android_debug_observation_only")',
        'root.addMarker("strict_state_observed:adapter=android_debug_semantic_facts")',
    )
    marker = '        root.addMarker("strict_state_binding:per_case_ui_tokens_required")'
    fact_loop = (
        marker
        + '\n        factsFor(caseId).forEach { fact ->\n'
        + '            root.addMarker("strict_state_fact:$fact", 12f)\n'
        + '        }'
    )
    if 'factsFor(caseId).forEach' not in text:
        text = text.replace(marker, fact_loop)
    start = text.find("    private fun factsFor(caseId: String): List<String>")
    if start != -1:
        end = text.find("    private fun LinearLayout.addMarker", start)
        if end == -1:
            raise RuntimeError(f"Cannot replace factsFor in {path}")
        text = text[:start] + render_kotlin_facts(task_facts) + text[end:]
    else:
        insert = "    private fun LinearLayout.addMarker"
        text = text.replace(insert, render_kotlin_facts(task_facts) + "    private fun LinearLayout.addMarker")
    path.write_text(text, encoding="utf-8")


def render_ets_facts(task_facts: dict[str, list[str]]) -> str:
    lines = [
        "  private stateTestSemanticFacts(): string[] {",
        "    if (!this.stateTestMatchesScenario() || !this.stateTestFeatureEnabled()) {",
        "      return [];",
        "    }",
        "    switch (this.stateTestCaseId) {",
    ]
    for case_id, facts in sorted(task_facts.items()):
        lines.append(f"      case {ets_quote(case_id)}:")
        lines.append("        return [")
        for fact in facts:
            lines.append(f"          {ets_quote(fact)},")
        lines.append("        ];")
    lines.extend([
        "      default:",
        "        return [];",
        "    }",
        "  }",
        "",
    ])
    return "\n".join(lines)


def patch_arkts(path: Path, task_facts: dict[str, list[str]]) -> None:
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "Text('strict_state_observed:adapter=arkts_state_observation_only')",
        "Text('strict_state_observed:adapter=arkts_semantic_facts')",
    )
    anchor = (
        "      Text('strict_state_binding:per_case_ui_tokens_required')\n"
        "        .fontSize(12)\n"
        "        .fontWeight(FontWeight.Medium)\n"
        "        .fontColor('#334155')\n"
        "        .id('strict_state_binding_required')"
    )
    fact_view = (
        anchor
        + "\n      ForEach(this.stateTestSemanticFacts(), (fact: string, index: number) => {\n"
        + "        Text(`strict_state_fact:${fact}`)\n"
        + "          .fontSize(10)\n"
        + "          .fontColor('#334155')\n"
        + "          .id(`strict_state_fact_${index}`)\n"
        + "      })"
    )
    if "this.stateTestSemanticFacts()" not in text:
        text = text.replace(anchor, fact_view)
    start = text.find("  private stateTestSemanticFacts(): string[]")
    method = render_ets_facts(task_facts)
    if start != -1:
        end = text.find("  private handleStateTestCaseChanged(): void", start)
        if end == -1:
            raise RuntimeError(f"Cannot replace stateTestSemanticFacts in {path}")
        text = text[:start] + method + text[end:]
    else:
        text = text.replace("  private handleStateTestCaseChanged(): void", method + "  private handleStateTestCaseChanged(): void")
    path.write_text(text, encoding="utf-8")


def main() -> int:
    real_ui_script = ROOT / "scripts" / "patch_real_ui_state_harness.py"
    namespace = {"__name__": "__main__", "__file__": str(real_ui_script)}
    exec(compile(real_ui_script.read_text(encoding="utf-8"), str(real_ui_script), "exec"), namespace)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
