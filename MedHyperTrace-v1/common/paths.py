"""Central config for data + repo locations. Override the dataset dir with the
MHT_DATA_DIR env var; otherwise it defaults to <repo>/data/AEGIS-custom-dataset."""
import os

COMMON_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(COMMON_DIR)

DATA_DIR = os.environ.get(
    "MHT_DATA_DIR", os.path.join(REPO_ROOT, "data", "AEGIS-custom-dataset")
)

FILES = {
    "mdagents":  os.path.join(DATA_DIR, "medxpertqa-mm-100-mdagents_error.jsonl"),
    "dylan":     os.path.join(DATA_DIR, "mmlu_pro_health-100-dylan_error.jsonl"),
    "llm_debate": os.path.join(DATA_DIR, "mmlu_pro_health-100-llm_debate_error.jsonl"),
    "clinical_agent": os.path.join(DATA_DIR, "trial_success-200-clinical_agent_error.jsonl"),
    "clinical_agent5": os.path.join(DATA_DIR, "trial_success-200-500-clinical_agent5_error.jsonl"),
}

SPLITS_JSON = os.path.join(COMMON_DIR, "splits.json")
