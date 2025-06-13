# Code_reviewer_v1
Trying to create an integrated AI agent that will perform code review for every commit

## Automated AI Code Reviewer

This repository integrates an **AI-powered code review** that runs automatically after every commit and produces detailed feedback using OpenAI's `o3` model.

### Quick start

1.  Install dependencies (ideally inside a virtualenv):

    ```bash
    pip install -r requirements.txt
    ```

2.  Export your OpenAI credentials:

    ```bash
    export OPENAI_API_KEY="sk-..."  # replace with your key
    ```

3.  Activate the version-controlled Git hooks:

    ```bash
    # Tell Git to use hooks from the .githooks/ directory
    git config core.hooksPath .githooks
    # Make sure the hook has execute permissions (once)
    chmod +x .githooks/post-commit
    ```

From now on, **every commit** will trigger a post-commit hook that

* Collects the diff of the commit plus a snapshot (up to `MAX_CONTEXT_CHARS`) of the repository.
* Sends this information to the OpenAI API with the `o3` model.
* Prints an actionable, line-referenced review to your terminal.

### Configuration

Environment variables:

* `OPENAI_API_KEY` – **required**. Your OpenAI API key.
* `MODEL` – Model name to use (default: `o3`).
* `MAX_CONTEXT_CHARS` – Maximum characters of repository context to send (default: `100000`).

You can also invoke the reviewer manually:

```bash
python scripts/ai_code_reviewer.py --commit <hash> [--no-context]
```
