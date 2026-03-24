import os

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 8096

BASE_DIR = os.path.dirname(__file__)
INPUT_DIR = os.path.join(BASE_DIR, "inputs")
ARTIFACTS_DIR = os.path.join(INPUT_DIR, "sample_artifacts")
DOCS_DIR = os.path.join(INPUT_DIR, "docs")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
INPUT_CONFIG_PATH = os.path.join(INPUT_DIR, "input_config.yaml")

MAX_QUESTION_ROUNDS = 5
QUESTIONS_PER_BATCH = 5

MAX_PAGES_PER_URL = 15
MAX_CONTENT_PER_PAGE = 12000
SCRAPE_TIMEOUT = 30
SCRAPE_DELAY = 1.0
