import os
from dotenv import load_dotenv
load_dotenv()

AZURE_AI_FOUNDRY_ENDPOINT = os.environ.get("AZURE_AI_FOUNDRY_ENDPOINT", "")
AZURE_AI_FOUNDRY_API_KEY = os.environ.get("AZURE_AI_FOUNDRY_API_KEY", "")
MODEL = "claude-sonnet-4-5"
MAX_TOKENS = 16000         # per API call — keeps responses within Azure gateway timeout
ENRICHMENT_MAX_TOKENS = 16000  # enrichment rewrites targeted sections, same budget

BASE_DIR = os.path.dirname(__file__)
INPUT_DIR = os.path.join(BASE_DIR, "inputs")
ARTIFACTS_DIR = os.path.join(INPUT_DIR, "sample_artifacts")
DOCS_DIR = os.path.join(INPUT_DIR, "docs")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
INPUT_CONFIG_PATH = os.path.join(INPUT_DIR, "input_config.yaml")

MAX_QUESTION_ROUNDS = 5
MAX_AREAS_PER_ROUND = 5

MAX_PAGES_PER_URL = 15
MAX_CONTENT_PER_PAGE = 12000
SCRAPE_TIMEOUT = 30
SCRAPE_DELAY = 1.0
