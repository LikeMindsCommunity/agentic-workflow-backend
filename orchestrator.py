"""
Main orchestration loop for the KB builder pipeline.
"""
import json
import os
import re
import sys
import time
from pathlib import Path

import config
from agents.draft import run_draft_agent
from agents.interrogator import run_interrogator_agent
from agents.enrichment import run_enrichment_agent
from utils.file_loader import load_input_config, detect_input_mode
from utils.kb_utils import make_kb_path, count_dir_files
from utils.cli import print_header, print_step, display_areas, collect_user_input


async def main():
    print_header()

    cfg = load_input_config()
    prompt = cfg.get("prompt", "")

    if not prompt:
        print("\n  [ERROR] No prompt found in input_config.yaml")
        sys.exit(1)

    mode = detect_input_mode(config.ARTIFACTS_DIR, config.DOCS_DIR, prompt)

    artifact_count = count_dir_files(config.ARTIFACTS_DIR)
    doc_count = count_dir_files(config.DOCS_DIR)

    print(f"\n  Mode     : {mode}")
    print(f"  Artifacts: {artifact_count}")
    print(f"  Docs     : {doc_count} local")
    print(f"\n  User Prompt Preview:")
    print(f"  {prompt[:150]}{'...' if len(prompt) > 150 else ''}\n")

    if mode == "empty":
        print(
            "\n  [ERROR] No inputs found. Provide a prompt in input_config.yaml"
            " and/or add files to inputs/sample_artifacts/ or inputs/docs/"
        )
        sys.exit(1)

    # Phase 1: Draft
    print_step("Draft Phase")
    print("  Running Draft Agent...")
    start = time.time()
    kb_path, safe_name = await run_draft_agent(prompt, mode)
    print(f"  Draft completed in {time.time() - start:.1f}s")

    # Refinement loop
    round_num = 0
    while True:
        round_num += 1
        print_step(f"Gap Analysis — Round {round_num}")

        print("  Running Interrogator Agent...")
        start = time.time()
        try:
            areas_data = await run_interrogator_agent(kb_path, mode)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"\n  [ERROR] Interrogator returned invalid output: {e}")
            retry = input("  Retry this round? (y/n): ").strip().lower()
            if retry == "y":
                round_num -= 1
                continue
            break

        print(f"  Interrogator completed in {time.time() - start:.1f}s")
        areas = areas_data.get("areas", [])
        ready = areas_data.get("ready_for_generation", False)

        if areas:
            if ready:
                print("\n  ✓ No blocking gaps — but here are areas you could still improve:")
            display_areas(areas_data)
            print("\n  For each area: paste a URL, type 'file' if you've added docs,")
            print("  or just explain it. Type 'done' when you have nothing more to add.")
        else:
            print("\n  No gaps identified.")
            print("  Type 'done' to finish, or share anything else you'd like to add.")

        while True:
            user_input, user_done = collect_user_input()

            if user_done:
                break

            if user_input.strip():
                break

            print("\n  Nothing provided. Type 'done' to finish, or share info for one of the areas above.")

        if user_done:
            break

        print_step(f"Enrichment — Round {round_num}")
        print("  Running Enrichment Agent...")
        start = time.time()
        kb_path = await run_enrichment_agent(kb_path, user_input, safe_name, round_num)
        print(f"  Enrichment completed in {time.time() - start:.1f}s")

    # Final save
    final_path = make_kb_path(safe_name, "FINAL")
    content = Path(kb_path).read_text(encoding="utf-8")
    Path(final_path).write_text(content, encoding="utf-8")

    match = re.search(r'<!--\s*PLATFORM:\s*(.+?)\s*-->', content[:500])
    platform_name = match.group(1) if match else safe_name

    verifications = content.lower().count("needs verification")

    print(f"\n{'=' * 60}")
    print(f"  Platform       : {platform_name}")
    print(f"  Mode           : {mode}")
    print(f"  Rounds         : {round_num}")
    print(f"  Output         : {final_path}")
    print(f"  Remaining gaps : {verifications} 'Needs Verification' items")
    print(f"{'=' * 60}\n")
