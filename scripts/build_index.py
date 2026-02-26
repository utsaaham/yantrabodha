#!/usr/bin/env python3
"""
Build a searchable index of all experiences.
Generates:
  - index.json: Lightweight index with titles, tags, IDs for fast search
  - stats.json: Repository statistics
"""

import json
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

EXPERIENCES_DIR = Path(__file__).parent.parent / "experiences"
INDEX_PATH = Path(__file__).parent.parent / "index.json"
STATS_PATH = Path(__file__).parent.parent / "stats.json"


def build_index():
    entries = []
    tags_counter = Counter()
    lang_counter = Counter()
    type_counter = Counter()
    agent_counter = Counter()

    for json_file in sorted(EXPERIENCES_DIR.rglob("*.json")):
        try:
            with open(json_file) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        # Build lightweight index entry
        entry = {
            "id": data.get("id", ""),
            "type": data.get("type", ""),
            "title": data.get("title", ""),
            "language": data.get("language", ""),
            "tags": data.get("tags", []),
            "confidence": data.get("metadata", {}).get("confidence", ""),
            "verified": data.get("metadata", {}).get("verified", False),
            "verification_count": data.get("metadata", {}).get("verification_count", 0),
            "agent": data.get("metadata", {}).get("contributing_agent", ""),
            "submitted_at": data.get("metadata", {}).get("submitted_at", ""),
            "path": str(json_file.relative_to(EXPERIENCES_DIR.parent)),
        }

        # Add error message snippet for search
        if data.get("error", {}).get("message"):
            entry["error_snippet"] = data["error"]["message"][:200]

        entries.append(entry)

        # Count stats
        for tag in data.get("tags", []):
            tags_counter[tag] += 1
        lang_counter[data.get("language", "unknown")] += 1
        type_counter[data.get("type", "unknown")] += 1
        agent_counter[data.get("metadata", {}).get("contributing_agent", "unknown")] += 1

    # Write index
    index = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_experiences": len(entries),
        "entries": entries,
    }
    with open(INDEX_PATH, "w") as f:
        json.dump(index, f, indent=2)

    # Write stats
    stats = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_experiences": len(entries),
        "by_type": dict(type_counter.most_common()),
        "by_language": dict(lang_counter.most_common()),
        "by_agent": dict(agent_counter.most_common()),
        "top_tags": dict(tags_counter.most_common(30)),
        "verified_count": sum(1 for e in entries if e.get("verified")),
    }
    with open(STATS_PATH, "w") as f:
        json.dump(stats, f, indent=2)

    print(f"Index built: {len(entries)} experiences")
    print(f"Languages: {dict(lang_counter.most_common(5))}")
    print(f"Types: {dict(type_counter)}")
    print(f"Agents: {dict(agent_counter.most_common(5))}")


if __name__ == "__main__":
    build_index()
