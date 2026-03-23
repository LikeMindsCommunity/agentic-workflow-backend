# LikeMinds Layer 1 - Platform Knowledge Base Builder

An agentic workflow that reverse-engineers client platform artifacts and builds a structured knowledge base for automated artifact generation.

## How It Works

1. **You provide inputs**: Drop sample artifacts and (optionally) documentation into the `inputs/` folder
2. **Analyzer agent** decomposes the artifacts, maps them against any docs, and produces a draft knowledge base with confidence scores
3. **Interrogator agent** reviews the knowledge base, identifies gaps, and generates targeted questions
4. **You answer questions** through the CLI - the system feeds your answers back into the knowledge base
5. **Loop repeats** until the knowledge base reaches sufficient confidence
6. **Final output**: A structured `.md` knowledge base (+ companion JSON) ready for Layer 2's deployment engine

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your API key
export ANTHROPIC_API_KEY=your-key-here

# 3. Add your inputs (see Input Modes below)
```

## Input Modes

Layer 1 supports three input combinations. Mix and match as needed.

### Mode 1: Artifacts + local documentation files
Drop your sample artifacts and documentation files directly into the input folders:
```
inputs/
  sample_artifacts/   ← drop JSON, config files, etc. here
  docs/               ← drop .md, .txt, .json docs here
```

### Mode 2: Artifacts + documentation URLs
Create `inputs/docs/urls.txt` listing one documentation URL per line.
Layer 1 will fetch each page and use it as documentation.
```
# inputs/docs/urls.txt
https://docs.yourplatform.com/api/workflows
https://docs.yourplatform.com/api/nodes
# lines starting with # are ignored
```
You can also mix local doc files and URLs — both are loaded.

### Mode 3: Artifacts only (no documentation)
Drop only sample artifacts in `inputs/sample_artifacts/` — no docs needed.
The Interrogator switches to a comprehensive discovery mode and asks
foundational questions to build the entire knowledge base from scratch.

### Optional: Requirements / scope file
Create `inputs/requirements.md` to tell the agents what to focus on.
```markdown
# Requirements
We need to understand the IVR workflow artifact well enough to generate
new workflows for inbound customer-support flows.

Focus on: node types, routing logic, and audio prompt fields.
Out of scope: analytics and reporting fields.
```

## Usage

```bash
python main.py
```

The system will:
- Detect which input mode you are using
- Run analysis (30-60s)
- Show the knowledge base assessment
- Ask questions about gaps it found
- Update the knowledge base with your answers
- Repeat until confident or you choose to stop

## Output

Final outputs are saved in `outputs/`:

| File | Purpose |
|------|---------|
| `knowledge_base_FINAL_<timestamp>.md` | Human-readable knowledge base (primary output) |
| `knowledge_base_FINAL_<timestamp>.json` | Machine-readable knowledge base for Layer 2 |
| `kb_snapshot_r<N>_<timestamp>.json` | Intermediate snapshots after each Q&A round |

## Project Structure

```
likeminds-layer1/
  main.py                  # Orchestrator and CLI
  config.py                # Settings (model, paths, thresholds)
  requirements.txt
  agents/
    analyzer.py            # Artifact analysis and knowledge mapping
    interrogator.py        # Gap detection and question generation
  models/
    knowledge_base.py      # Knowledge base data models
  utils/
    file_loader.py         # Input loading (local files + URL fetching)
    kb_formatter.py        # Converts KB dict → Markdown
  inputs/
    sample_artifacts/      # Drop client artifacts here
    docs/                  # Drop docs here (or add urls.txt)
    requirements.md        # Optional: scope definition
  outputs/                 # Generated knowledge bases land here
```

## Configuration

Edit `config.py` to adjust:
- `MODEL`: Which Claude model to use
- `MAX_QUESTION_ROUNDS`: Max Q&A loops before stopping
- `QUESTIONS_PER_BATCH`: How many questions per round
- `CONFIDENCE_THRESHOLD`: Below this triggers questions (0-1)
- `REQUIREMENTS_FILE`: Path to the optional requirements file
- `DOCS_URLS_FILE`: Path to the optional URL list file

## Knowledge Base Output Format (Markdown)

The `.md` output is a fully structured document covering:

- **Overview table** — platform, artifact type, overall confidence, counts
- **Objects** — each top-level entity with a field table and collapsible detail sections (valid values, constraints, defaults, dependencies)
- **Dependencies** — ordering constraints between objects
- **Validation Rules** — cross-field business rules with severity badges
- **Common Patterns** — recurring structures observed in the artifacts
- **Open Gaps** — unresolved unknowns grouped by severity (blocking / important / nice-to-have)

The companion `.json` file follows the same structure and is consumed by Layer 2.
