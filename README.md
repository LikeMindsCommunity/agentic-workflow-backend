# LikeMinds Layer 1 - Platform Knowledge Base Builder

Two-agent system that builds structured markdown knowledge bases from client platform inputs.

## Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your-key-here
```

## Usage

**1. Edit `inputs/input_config.yaml` with what you have:**

```yaml
platform_name: "Exotel IVR"

scope: |
  We want to automate creation of IVR nodeflow JSON files.

artifacts_dir: "sample_artifacts"   # drop files in inputs/sample_artifacts/
docs_dir: "docs"                    # drop files in inputs/docs/

doc_urls:                           # or provide documentation website links
  - "https://developer.exotel.com/api/nodeflows"
```

**2. Run:**

```bash
python main.py
```

**3. Respond to knowledge area gaps.** The system groups related unknowns into areas (not individual questions). For each area you can:

- Paste a **URL** (starts with http) and the system scrapes it on the spot
- Type **`file`** if you've added new docs to `inputs/docs/` since the run started
- Type a **text explanation** (multi-line supported, empty line to finish)
- Type `skip` to skip or `done` to end the round

This means one response can resolve dozens of individual gaps at once.

## Input Modes

The system auto-detects what you provided and adapts:

- **Full** - artifacts + docs. Best results, fewest gaps.
- **Artifacts only** - no docs. Agent reverse-engineers and asks for doc sources.
- **Docs/URLs only** - no artifacts. Agent builds from docs, asks for samples.
- **Scope only** - just a description. Agent asks foundational questions.

## Output

A single `.md` file in `outputs/` per platform. Intermediate versions saved after each round.

## Project Structure

```
likeminds-layer1/
  main.py                    # orchestrator and CLI
  config.py                  # settings
  agents/
    analyzer.py              # writes/rewrites the KB markdown
    interrogator.py          # finds knowledge area gaps
  utils/
    file_loader.py           # input loading, mode detection, mid-loop reload
    web_scraper.py           # doc URL scraping
  inputs/
    input_config.yaml        # your input configuration
    sample_artifacts/        # client artifacts here
    docs/                    # client docs here
  outputs/                   # generated knowledge bases
```
