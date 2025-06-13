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

import argparse
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import List

import openai

# ----------------------------- Helpers ------------------------------------- #

def run(cmd: List[str], cwd: Path | None = None) -> str:
    """Run a shell command and return its stdout decoded as UTF-8."""
    result = subprocess.run(cmd, cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
        if path.is_dir():
            if path.name in EXCLUDE_DIRS:
                # Skip entire directory
                dirs_to_skip = [p for p in path.glob("**/*")]
                continue
            continue

        if path.suffix.lower() in EXCLUDE_EXTENSIONS:
            continue

        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            # Probably a binary file
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
        print(f"Error obtaining diff for commit {commit_hash}: {exc.stderr.decode()}", file=sys.stderr)
        sys.exit(1)
    return diff_output


def build_messages(diff: str, context: str | None) -> List[dict[str, str]]:
    """Compose chat messages for the OpenAI API call."""
    system_msg = (
        "You are an experienced senior software engineer and code reviewer. "
        "Given a commit diff and the project context, produce a thorough, actionable "
        "code review. Highlight potential bugs, code smells, documentation gaps, "
        "performance issues, security concerns, and suggest concrete improvements. "
        "Reference specific files and line numbers where appropriate. Be concise but "
        "comprehensive."
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

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Environment variable OPENAI_API_KEY is not set.", file=sys.stderr)
        sys.exit(1)

    openai.api_key = api_key
    model = os.getenv("MODEL", "o3")

    diff = get_commit_diff(args.commit)

    context = None
    max_chars = int(os.getenv("MAX_CONTEXT_CHARS", "100000"))
    if not args.no_context:
        repo_root = Path(__file__).resolve().parent.parent
        context = collect_repo_context(repo_root, max_chars=max_chars)

    messages = build_messages(diff, context)

    try:
        response = openai.ChatCompletion.create(
            model=model,
            messages=messages,
            temperature=0.2,
        )
    except Exception as exc:
        print(f"OpenAI API error: {exc}", file=sys.stderr)
        sys.exit(1)

    review = response.choices[0].message["content"].strip()
    print("\n=== AI CODE REVIEW ===\n")
    print(review)


if __name__ == "__main__":
    main() 