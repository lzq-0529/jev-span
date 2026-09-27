#!/usr/bin/env bash
# Fetch the public NER datasets used by bench/prepare.py into bench/data/ (about 60 MB).
# Each dataset keeps its own license; nothing downloaded here is redistributed by this repository.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p data

get() {
  curl -sfL --retry 3 -o "data/$1" "$2"
  echo "data/$1"
}
hf() { get "$2" "https://huggingface.co/datasets/$1/resolve/main/$3"; }

hf PassbyGrocer/msra-ner msra_train.parquet data/train-00000-of-00001.parquet
hf PassbyGrocer/msra-ner msra_test.parquet data/test-00000-of-00001.parquet
hf PassbyGrocer/resume-ner resume_dev.parquet data/validation-00000-of-00001.parquet
hf PassbyGrocer/resume-ner resume_test.parquet data/test-00000-of-00001.parquet
hf PassbyGrocer/weibo-ner weibo_dev.parquet data/validation-00000-of-00001.parquet
hf PassbyGrocer/weibo-ner weibo_test.parquet data/test-00000-of-00001.parquet
hf xusenlin/clue-ner cluener_train.parquet data/train-00000-of-00001-39fc4e004146ece2.parquet
hf xusenlin/clue-ner cluener_dev.parquet data/validation-00000-of-00001-bc5663be3b7ff2cd.parquet
hf tomaarsen/conll2003 conll_dev.parquet data/validation-00000-of-00001.parquet
hf tomaarsen/conll2003 conll_test.parquet data/test-00000-of-00001.parquet

for name in wnut:wnut2017 mitres:mit_restaurant; do
  short=${name%%:*}
  repo=${name#*:}
  hf "tner/$repo" "${short}_label.json" dataset/label.json
  for split in valid test; do
    hf "tner/$repo" "${short}_${split}.json" "dataset/${split}.json"
  done
done

for dom in ai literature music politics science; do
  for split in validation test; do
    get "crossner_${dom}_${split}.parquet" \
      "https://huggingface.co/api/datasets/DFKI-SLT/cross_ner/parquet/${dom}/${split}/0.parquet"
  done
done
