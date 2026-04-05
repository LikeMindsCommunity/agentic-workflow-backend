"""
CLI display and user interaction helpers.
"""


def print_header():
    print("\n" + "=" * 60)
    print("  LikeMinds Layer 1 - Knowledge Base Builder")
    print("=" * 60)


def print_step(label: str):
    print(f"\n{'~' * 60}")
    print(f"  {label}")
    print(f"{'~' * 60}")


def display_areas(areas_data: dict):
    print(f"\n{'=' * 60}")
    print("  KNOWLEDGE BASE ASSESSMENT")
    print(f"{'=' * 60}")
    print(f"\n  {areas_data.get('summary', '')}")
    ready = areas_data.get("ready_for_generation", False)
    print(f"\n  Ready for Use: {'YES ✓' if ready else 'NO'}")

    areas = areas_data.get("areas", [])
    if not areas:
        print("\n  No gaps identified.")
        return

    priority_groups = [
        ("BLOCKING — use case cannot proceed without this", "blocking"),
        ("IMPORTANT — affects correctness", "important"),
        ("NICE TO HAVE — completeness", "nice_to_have"),
    ]
    for group_label, priority in priority_groups:
        group = [a for a in areas if a.get("priority") == priority]
        if not group:
            continue
        print(f"\n  --- {group_label} ---")
        for a in group:
            print(f"\n    [{a['id']}] {a['title']}")
            print(f"         We have: {a.get('what_we_have', '')}")
            print(f"         We need: {a.get('what_we_need', '')}")
            print(f"         Source:  {a.get('suggested_sources', '')}")


def collect_user_input() -> tuple[str, bool]:
    """
    Collect free-form user input after gaps are displayed.
    Returns (user_input, user_done).
    user_done=True when the user typed 'done' — caller should skip enrichment.
    """
    print(f"\n{'~' * 60}")
    print("  Paste a URL, type 'file' if you dropped docs into inputs/docs/,")
    print("  explain in plain text, or type 'done' to finish.")
    print("  (Enter once to submit. For multi-line input, end with a blank line.)")
    print(f"{'~' * 60}\n")

    lines = []
    while True:
        try:
            line = input("  > ").strip()
        except EOFError:
            break
        if line.lower() == "done":
            return "", True
        if not line:
            if lines:
                break
            continue
        lines.append(line)
        break

    while lines:
        try:
            line = input("  > ").strip()
        except EOFError:
            break
        if not line:
            break
        if line.lower() == "done":
            return "", True
        lines.append(line)

    return "\n".join(lines), False
