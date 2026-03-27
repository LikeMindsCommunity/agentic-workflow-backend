import os
from dotenv import load_dotenv
load_dotenv()

AZURE_AI_FOUNDRY_ENDPOINT = os.environ.get("AZURE_AI_FOUNDRY_ENDPOINT", "")
AZURE_AI_FOUNDRY_API_KEY = os.environ.get("AZURE_AI_FOUNDRY_API_KEY", "")
MODEL = "claude-sonnet-4-5"
MAX_TOKENS = 64000

BASE_DIR = os.path.dirname(__file__)
INPUT_DIR = os.path.join(BASE_DIR, "inputs")
ARTIFACTS_DIR = os.path.join(INPUT_DIR, "sample_artifacts")
DOCS_DIR = os.path.join(INPUT_DIR, "docs")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
INPUT_CONFIG_PATH = os.path.join(INPUT_DIR, "input_config.yaml")

MAX_AREAS_PER_ROUND = 5
