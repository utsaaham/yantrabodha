#!/usr/bin/env python3
"""
Yantrabodha PR Validation Script
=================================
Validates experience JSON files against the schema and checks for:
- Schema compliance
- Duplicate IDs
- Prompt injection patterns
- Sensitive data leaks
- Content quality signals

Usage:
    python validate.py <file_path>              # Validate a single file
    python validate.py --all                     # Validate all experiences
    python validate.py --changed                 # Validate changed files (for CI)
"""

import json
import sys
import re
import os
from pathlib import Path
from typing import List, Tuple

# =============================================================================
# Configuration
# =============================================================================

SCHEMA_PATH = Path(__file__).parent.parent / "schema" / "experience.schema.json"
EXPERIENCES_DIR = Path(__file__).parent.parent / "experiences"

# Patterns that suggest prompt injection attempts
INJECTION_PATTERNS = [
    r"ignore\s+(previous|above|all)\s+(instructions|prompts|rules)",
    r"you\s+are\s+(now|a)\s+",
    r"system\s*prompt",
    r"<\s*(system|assistant|user)\s*>",
    r"\[\s*INST\s*\]",
    r"```\s*(system|instruction)",
    r"act\s+as\s+(if|a|an)\s+",
    r"pretend\s+(you|to)\s+",
    r"from\s+now\s+on",
    r"new\s+instructions",
    r"override\s+(all|previous|your)",
    r"execute\s+(this|the\s+following)\s+(code|command|script)",
    r"run\s+(this|the\s+following)\s+(code|command|script)",
    r"eval\s*\(",
    r"exec\s*\(",
    r"__import__",
    r"subprocess\.(run|call|Popen)",
    r"os\.system",
]

# Patterns that suggest leaked secrets
SECRET_PATTERNS = [
    r"(sk|pk|api|key|token|secret|password|credential)[_-]?(live|test|prod)?[_-]?\w{20,}",
    r"ghp_[A-Za-z0-9]{36}",           # GitHub PAT
    r"sk-[A-Za-z0-9]{48}",            # OpenAI key
    r"sk-ant-[A-Za-z0-9-]{90,}",      # Anthropic key
    r"eyJ[A-Za-z0-9_-]{50,}",         # JWT tokens
    r"AKIA[A-Z0-9]{16}",              # AWS access key
    r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----",
    r"mongodb(\+srv)?://\w+:\w+@",    # MongoDB connection strings
    r"postgres://\w+:\w+@",           # Postgres connection strings
]

# Minimum quality thresholds
MIN_TITLE_WORDS = 4
MIN_SOLUTION_WORDS = 10
MIN_ERROR_MESSAGE_LENGTH = 10


# =============================================================================
# Validation Functions
# =============================================================================


def load_schema() -> dict:
    """Load the JSON schema."""
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def validate_json_syntax(file_path: Path) -> Tuple[bool, str]:
    """Check if the file is valid JSON."""
    try:
        with open(file_path) as f:
            json.load(f)
        return True, ""
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {e}"


def validate_schema(data: dict, schema: dict) -> List[str]:
    """Basic schema validation without jsonschema dependency."""
    errors = []

    # Check required fields
    for field in schema.get("required", []):
        if field not in data:
            errors.append(f"Missing required field: '{field}'")

    # Check field types and constraints
    props = schema.get("properties", {})

    if "id" in data:
        pattern = props.get("id", {}).get("pattern", "")
        if pattern and not re.match(pattern, data["id"]):
            errors.append(f"Invalid ID format: '{data['id']}' (must be kebab-case)")

    if "type" in data:
        valid_types = props.get("type", {}).get("enum", [])
        if valid_types and data["type"] not in valid_types:
            errors.append(f"Invalid type: '{data['type']}' (must be one of {valid_types})")

    if "title" in data:
        title = data["title"]
        min_len = props.get("title", {}).get("minLength", 0)
        max_len = props.get("title", {}).get("maxLength", 9999)
        if len(title) < min_len:
            errors.append(f"Title too short (min {min_len} chars)")
        if len(title) > max_len:
            errors.append(f"Title too long (max {max_len} chars)")

    if "language" in data:
        valid_langs = props.get("language", {}).get("enum", [])
        if valid_langs and data["language"] not in valid_langs:
            errors.append(f"Invalid language: '{data['language']}'")

    if "tags" in data:
        if not isinstance(data["tags"], list) or len(data["tags"]) < 1:
            errors.append("Must have at least 1 tag")
        for tag in data.get("tags", []):
            if not re.match(r'^[a-z0-9-]{1,50}$', tag):
                errors.append(f"Invalid tag format: '{tag}' (must be lowercase kebab-case)")

    # Type-specific validation
    if data.get("type") == "error":
        if "error" not in data:
            errors.append("Error-type experiences must include 'error' object")
        if "solution" not in data:
            errors.append("Error-type experiences must include 'solution' object")

    if "metadata" in data:
        meta = data["metadata"]
        for req in ["contributing_agent", "confidence", "submitted_at"]:
            if req not in meta:
                errors.append(f"Missing required metadata field: '{req}'")

    return errors


def check_prompt_injection(data: dict) -> List[str]:
    """Scan all text fields for prompt injection patterns."""
    warnings = []
    text_content = json.dumps(data).lower()

    for pattern in INJECTION_PATTERNS:
        matches = re.findall(pattern, text_content, re.IGNORECASE)
        if matches:
            warnings.append(f"⚠️  Possible prompt injection detected: pattern '{pattern}' matched")

    return warnings


def check_secrets(data: dict) -> List[str]:
    """Scan for leaked secrets and credentials."""
    warnings = []
    text_content = json.dumps(data)

    for pattern in SECRET_PATTERNS:
        if re.search(pattern, text_content):
            warnings.append(f"🔑 Possible secret/credential detected: pattern '{pattern}'")

    return warnings


def check_quality(data: dict) -> List[str]:
    """Check content quality signals."""
    warnings = []

    title = data.get("title", "")
    if len(title.split()) < MIN_TITLE_WORDS:
        warnings.append(f"Title should be at least {MIN_TITLE_WORDS} words for searchability")

    solution = data.get("solution", {})
    if solution:
        desc = solution.get("description", "")
        if len(desc.split()) < MIN_SOLUTION_WORDS:
            warnings.append(f"Solution description should be at least {MIN_SOLUTION_WORDS} words")

    error = data.get("error", {})
    if error:
        msg = error.get("message", "")
        if len(msg) < MIN_ERROR_MESSAGE_LENGTH:
            warnings.append("Error message seems too short to be useful")

    return warnings


def check_duplicate_id(data: dict) -> List[str]:
    """Check if the experience ID already exists."""
    warnings = []
    exp_id = data.get("id", "")
    if not exp_id:
        return warnings

    for json_file in EXPERIENCES_DIR.rglob("*.json"):
        try:
            with open(json_file) as f:
                existing = json.load(f)
            if existing.get("id") == exp_id and json_file.name != f"{exp_id}.json":
                warnings.append(f"Duplicate ID '{exp_id}' found in {json_file}")
        except (json.JSONDecodeError, OSError):
            continue

    return warnings


def validate_file(file_path: Path) -> Tuple[bool, List[str], List[str]]:
    """
    Validate a single experience file.
    Returns: (is_valid, errors, warnings)
    """
    errors = []
    warnings = []

    # Step 1: JSON syntax
    valid, msg = validate_json_syntax(file_path)
    if not valid:
        return False, [msg], []

    with open(file_path) as f:
        data = json.load(f)

    schema = load_schema()

    # Step 2: Schema validation
    errors.extend(validate_schema(data, schema))

    # Step 3: Security checks (these are errors, not warnings)
    injection_issues = check_prompt_injection(data)
    if injection_issues:
        errors.extend(injection_issues)

    secret_issues = check_secrets(data)
    if secret_issues:
        errors.extend(secret_issues)

    # Step 4: Quality checks (warnings, not blockers)
    warnings.extend(check_quality(data))

    # Step 5: Duplicate check
    dup_issues = check_duplicate_id(data)
    warnings.extend(dup_issues)

    is_valid = len(errors) == 0
    return is_valid, errors, warnings


# =============================================================================
# CLI
# =============================================================================


def main():
    if len(sys.argv) < 2:
        print("Usage: python validate.py <file_path> | --all | --changed")
        sys.exit(1)

    arg = sys.argv[1]

    if arg == "--all":
        files = list(EXPERIENCES_DIR.rglob("*.json"))
    elif arg == "--changed":
        # Get changed files from git
        import subprocess
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACMR", "HEAD~1", "HEAD"],
            capture_output=True, text=True
        )
        files = [
            Path(f) for f in result.stdout.strip().split("\n")
            if f.startswith("experiences/") and f.endswith(".json")
        ]
    else:
        files = [Path(arg)]

    if not files:
        print("No files to validate.")
        sys.exit(0)

    total_errors = 0
    total_warnings = 0

    for file_path in files:
        if not file_path.exists():
            print(f"❌ File not found: {file_path}")
            total_errors += 1
            continue

        is_valid, errors, warnings = validate_file(file_path)

        if is_valid and not warnings:
            print(f"✅ {file_path}")
        elif is_valid:
            print(f"⚠️  {file_path} (valid with warnings)")
            for w in warnings:
                print(f"   {w}")
            total_warnings += len(warnings)
        else:
            print(f"❌ {file_path}")
            for e in errors:
                print(f"   ERROR: {e}")
            for w in warnings:
                print(f"   WARNING: {w}")
            total_errors += len(errors)
            total_warnings += len(warnings)

    print(f"\n{'='*60}")
    print(f"Files: {len(files)} | Errors: {total_errors} | Warnings: {total_warnings}")

    if total_errors > 0:
        print("VALIDATION FAILED")
        sys.exit(1)
    else:
        print("VALIDATION PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
