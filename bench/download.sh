#!/usr/bin/env bash
# Fetch the public NER test sets used by bench/prepare.py into bench/data/.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p data
hf() { curl -sfL -o "data/$2" "https://huggingface.co/datasets/$1/resolve/main/$3"; echo "data/$2"; }
hf PassbyGrocer/msra-ner msra_test.parquet data/test-00000-of-00001.parquet
hf PassbyGrocer/resume-ner resume_test.parquet data/test-00000-of-00001.parquet
hf xusenlin/clue-ner cluener_dev.parquet data/validation-00000-of-00001-bc5663be3b7ff2cd.parquet
hf tomaarsen/conll2003 conll_test.parquet data/test-00000-of-00001.parquet
