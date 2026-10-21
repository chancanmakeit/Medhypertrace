# Dataset location

Put the extracted medical MAS error-trajectory dataset here:

    data/AEGIS-custom-dataset/
        medxpertqa-mm-100-mdagents_error.jsonl
        mmlu_pro_health-100-dylan_error.jsonl
        mmlu_pro_health-100-llm_debate_error.jsonl

Extract from your archive:  `py7zr x AEGIS-custom-dataset.7z -o data/`

Or point anywhere via env var:  `export MHT_DATA_DIR=/abs/path/to/AEGIS-custom-dataset`
(Everything reads the path from common/paths.py, which honours MHT_DATA_DIR.)
