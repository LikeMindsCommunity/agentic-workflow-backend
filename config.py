import os

# Anthropic API
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4096

# Paths
INPUT_DIR = os.path.join(os.path.dirname(__file__), "inputs")
ARTIFACTS_DIR = os.path.join(INPUT_DIR, "sample_artifacts")
DOCS_DIR = os.path.join(INPUT_DIR, "docs")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "outputs")

# Optional scope/requirements file placed in inputs/
# Create this file to tell the agents what to focus on.
REQUIREMENTS_FILE = os.path.join(INPUT_DIR, "requirements.md")

# URL list for documentation: inputs/docs/urls.txt
# Add one URL per line; lines starting with # are comments.
DOCS_URLS_FILE = os.path.join(DOCS_DIR, "urls.txt")

# Agent settings
MAX_QUESTION_ROUNDS = 5
QUESTIONS_PER_BATCH = 5
CONFIDENCE_THRESHOLD = 0.8  # 0-1, below this triggers a question
