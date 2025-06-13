# Code Reviewer 🐙

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9%2B-blue" />
  <img src="https://img.shields.io/badge/License-MIT-green" />
  <img src="https://img.shields.io/badge/CI-Pytest%20passing-brightgreen" />
</p>

> **Automated AI-powered reviews for every commit.**  
> Powered by OpenAI's `o3-mini` model, delivered instantly in your terminal.

---

## ✨ Features

• **Zero-click reviews** – a Git *post-commit* hook captures each change and feeds it to the model.  
• **Full-context analysis** – sends the diff *and* a snapshot of the repo (truncated to a safe size).  
• **Actionable feedback** – flags bugs, smells, docs gaps, perf/security issues with line references.  
• **Model-agnostic** – default is `o3-mini`; override via `MODEL` env var.  
• **Friendly setup** – just add your `OPENAI_API_KEY` to a `.env` and commit as usual.  
• **Tested** – critical helper functions covered by `pytest`.

---

## 🚀 Quick Start

```bash
# 1) Install dependencies (virtualenv/pyenv recommended)
pip install -r requirements.txt

# 2) Provide your OpenAI credentials – *never* commit real keys!
cp .env.example .env           # then edit .env and add your key

# 3) Activate repo-local Git hooks (one-time)
./scripts/install_hooks.sh

# Done!  Make a commit and watch the ✨ appear.
```

---

## ⚙️ Configuration

Environment variable | Purpose | Default
--- | --- | ---
`OPENAI_API_KEY` | Your OpenAI key **(required)** | –
`MODEL` | Which model to use | `o3-mini`
`MAX_CONTEXT_CHARS` | Max characters of repo context to send | `100000`
`PROMPT_PATH` | Override system prompt by editing `scripts/prompt.md` | –
`RUN_TIMEOUT` | Timeout in seconds for git commands (0 to disable) | `10`
`PROMPT_FILE` | Path to custom system prompt markdown | `scripts/prompt.md`

All variables can live in your `.env` file (git-ignored).

---

## 🖐 Manual Invocation

Want to trigger a review outside the hook (e.g. in CI)?

```bash
python scripts/ai_code_reviewer.py --commit <hash> [--no-context]
```

---

## 🧪 Running Tests

```bash
pytest -q      # runs 3 fast unit tests
```

---

## 🔒 Security Notes

• `.env` is already in `.gitignore`; keep secrets out of Git.  
• Sample credentials live in `.env.example` for convenience.  
• The reviewer prints results to stdout; it never writes remote logs.

---

## 📄 License

This project is licensed under the MIT License – see [LICENSE](LICENSE) for details.