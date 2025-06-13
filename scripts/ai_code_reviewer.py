#!/usr/bin/env python3
"""
ai_code_reviewer.py
-------------------
Runs after each git commit (hook) and sends the commit diff together with the
full repository context to an OpenAI model (o3) for automated code review.
The script prints the model's feedback to stdout.

Environment variables:
  OPENAI_API_KEY   Your OpenAI API key. Required.
  MAX_CONTEXT_CHARS  Max characters of repo context to send (default: 100_000)
  MODEL            The OpenAI model to use (default: "o3")

Usage (normally invoked by git hook):
    python scripts/ai_code_reviewer.py --commit <commit_hash>

You can also pass --no-context to omit the repository context if desired.
"""

from __future__ import annotations

# pylint: disable=import-error
import argparse
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import List
import logging

import dotenv
from openai import OpenAI

# --------------------------------------------------------------------------- #
# Configuration helpers

# Path to an optional custom system prompt. Users can override via the environment
# variable `PROMPT_FILE`; otherwise we default to `scripts/prompt.md`.
PROMPT_PATH = Path(os.getenv("PROMPT_FILE", Path(__file__).with_name("prompt.md")))

# Timeout (in seconds) for shell commands executed via `run()`.
RUN_TIMEOUT = int(os.getenv("RUN_TIMEOUT", "10"))

# Basic debug logger that emits to stderr when DEBUG=1/true is set.
logging.basicConfig(level=logging.INFO if os.getenv("DEBUG") else logging.WARNING, format="%(message)s")

# ----------------------------- Helpers ------------------------------------- #

def run(cmd: List[str], cwd: Path | None = None, *, timeout: int | None = RUN_TIMEOUT) -> str:
    """Run a shell command and return its stdout decoded as UTF-8.

    A global timeout (via RUN_TIMEOUT env var) prevents hangs when Git is slow or
    waiting for user input. The timeout can be disabled by setting RUN_TIMEOUT=0.
    """
    kwargs = {
        "cwd": cwd,
        "check": True,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
    }
    if timeout and timeout > 0:
        kwargs["timeout"] = timeout

    result = subprocess.run(cmd, **kwargs)  # type: ignore[arg-type]
    return result.stdout.decode()


def collect_repo_context(repo_root: Path, max_chars: int) -> str:
    """Return a concatenated string with the contents of each text file in the repo.

    Large binary files and directories commonly not useful for code review are
    skipped. The resulting string is truncated to `max_chars` characters to
    avoid exceeding model context limits.
    """
    EXCLUDE_DIRS = {".git", "node_modules", "venv", "__pycache__", ".mypy_cache"}
    EXCLUDE_EXTENSIONS = {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".pdf",
        ".zip",
        ".gz",
        ".tar",
        ".sqlite",
    }

    context_chunks: List[str] = []
    current_len = 0

    for path in sorted(repo_root.rglob("*")):
        # Skip any file that resides inside an excluded directory (at any
        # depth) or whose own name matches an excluded directory.
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue

        if path.is_dir():
            # Directory entries themselves are not interesting as context.
            continue

        if path.suffix.lower() in EXCLUDE_EXTENSIONS:
            continue

        try:
            content = path.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001 – broad catch acceptable here
            logging.info("[AI Reviewer] Skipped non-text or unreadable file: %s (%s)", path, exc)
            continue

        chunk_header = f"\n\n# File: {path.relative_to(repo_root)}\n\n"
        chunk = chunk_header + content

        if current_len + len(chunk) > max_chars:
            # Stop if exceeding limit
            break

        context_chunks.append(chunk)
        current_len += len(chunk)

    return "".join(context_chunks)


def get_commit_diff(commit_hash: str) -> str:
    """Return the diff of the specified commit (against its parent)."""
    try:
        diff_output = run(["git", "show", "--unified=3", commit_hash])
    except subprocess.CalledProcessError as exc:
        # exc.stderr may be bytes or str depending on the Python version / platform
        stderr_msg = exc.stderr.decode() if isinstance(exc.stderr, (bytes, bytearray)) else str(exc.stderr)
        print(f"Error obtaining diff for commit {commit_hash}: {stderr_msg}", file=sys.stderr)
        sys.exit(1)
    return diff_output


def build_messages(diff: str, context: str | None) -> List[dict[str, str]]:
    """Compose chat messages for the OpenAI API call."""
    # Prefer external prompt file if it exists to make customization easy and
    # keep the inline default lightweight for token efficiency.
    if PROMPT_PATH.exists():
        system_msg = PROMPT_PATH.read_text().strip()
    else:
        system_msg = (
            "You are a senior Python code reviewer. Provide constructive, actionable feedback "
            "focused on readability, efficiency, security, testing, and maintainability. "
            "Reference file paths / line numbers from the diff. Respond with a brief summary "
            "followed by bullet-pointed issues and concrete suggestions. Praise positives too."
        )

    user_content = textwrap.dedent(
        f"""
        Here is the diff of the latest commit:
        ```diff
        {diff}
        ```
        """
    )

    if context:
        user_content += textwrap.dedent(
            f"""

            Here is additional project context (truncated if necessary):
            ```
            {context}
            ```
            """
        )

    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_content},
    ]


# ----------------------------- Main ---------------------------------------- #

def main() -> None:
    parser = argparse.ArgumentParser(description="Run AI code review on a git commit.")
    parser.add_argument("--commit", default="HEAD", help="Commit hash to review (default: HEAD)")
    parser.add_argument("--no-context", action="store_true", help="Skip sending full repo context")
    args = parser.parse_args()

    # Load environment variables from a local .env file (if present) so users
    # can avoid exporting OPENAI_API_KEY each session.
    dotenv.load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Environment variable OPENAI_API_KEY is not set.", file=sys.stderr)
        sys.exit(1)

    model = os.getenv("MODEL", "o3-mini")

    # Initialise OpenAI client. The v1 library exposes an `OpenAI` class that
    # encapsulates configuration like the API key. We prefer this over the
    # module-level globals because it supports multiple concurrent clients in
    # the same process (e.g. during unit tests) and makes dependency injection
    # straightforward if we ever mock the client.
    client = OpenAI(api_key=api_key)

    diff = get_commit_diff(args.commit)

    context = None
    max_chars = int(os.getenv("MAX_CONTEXT_CHARS", "100000"))
    if not args.no_context:
        repo_root = Path(__file__).resolve().parent.parent
        context = collect_repo_context(repo_root, max_chars=max_chars)

    messages = build_messages(diff, context)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
        )
    except Exception as exc:
        print(f"OpenAI API error: {exc}", file=sys.stderr)
        sys.exit(1)

    review = response.choices[0].message.content.strip()
    print("\n=== AI CODE REVIEW ===\n")
    print(review)


if __name__ == "__main__":
    main() 