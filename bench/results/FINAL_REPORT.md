
### Strict entity F1 (%) — standard metric

| Method | MSRA | Resume | CLUENER | Weibo | CoNLL03 | WNUT17 | MIT-Rest | CN-AI | CN-Lit | CN-Music | CN-Pol | CN-Sci | Avg 12 | Avg 8 EN |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Jev + our pipeline | 82.1 | 88.4 | 67.5 | 55.4 | 82.0 | 56.6 | 65.4 | 72.0 | 74.8 | 79.9 | 83.2 | 77.7 | 73.7 | 73.9 |
| Qwen3.8-27B prompt (API) | 72.0 | 90.0 | 63.6 | 48.9 | 86.2 | 54.0 | 73.8 | 69.2 | 72.5 | 81.0 | 76.8 | 76.9 | 72.1 | 73.8 |
| Qwen3-8B prompt (vLLM, 3090) | 62.2 | 68.5 | 55.9 | 35.5 | 74.8 | 38.8 | 43.4 | 53.2 | 52.4 | 70.7 | 56.5 | 57.2 | 55.7 | 55.9 |
| GLiNER2.5-multi | 55.2 | 56.2 | 31.1 | 27.9 | 64.5 | 51.4 | 44.1 | 43.3 | 56.4 | 64.1 | 58.7 | 52.5 | 50.4 | 54.4 |
| GLiNER-multi v2.1 | 50.5 | 21.1 | 30.3 | 22.5 | 58.4 | 43.3 | 27.8 | 47.3 | 62.6 | 71.5 | 66.5 | 62.3 | 47.0 | 55.0 |
| GLiNER-large v2.1 (EN only) | – | – | – | – | 53.1 | 39.5 | 47.2 | 49.8 | 60.2 | 71.7 | 64.1 | 64.8 | – | 56.3 |
| NuNER-Zero (EN only) | – | – | – | – | 59.1 | 41.6 | 35.9 | 50.7 | 60.4 | 70.2 | 72.3 | 60.8 | – | 56.4 |
| Fine-tuned BERT/RoBERTa (supervised) | 96.7 | 96.0 | 69.9 | 63.4 | 93.0 | 59.1 | 82.0 | – | – | – | – | – | – | – |

### Relaxed F1 (%) — overlap + same type

| Method | MSRA | Resume | CLUENER | Weibo | CoNLL03 | WNUT17 | MIT-Rest | CN-AI | CN-Lit | CN-Music | CN-Pol | CN-Sci | Avg 12 | Avg 8 EN |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Jev + our pipeline | 88.0 | 95.2 | 81.7 | 63.6 | 87.9 | 62.7 | 79.1 | 79.2 | 80.0 | 85.3 | 86.3 | 83.0 | 81.0 | 80.4 |
| Qwen3.8-27B prompt (API) | 80.0 | 96.0 | 75.1 | 59.6 | 87.5 | 61.6 | 85.5 | 76.1 | 76.0 | 85.0 | 81.4 | 80.8 | 78.7 | 79.2 |
| Qwen3-8B prompt (vLLM, 3090) | 67.6 | 77.7 | 65.5 | 44.0 | 76.1 | 47.3 | 54.8 | 57.8 | 56.3 | 75.1 | 61.2 | 61.1 | 62.0 | 61.2 |
| GLiNER2.5-multi | 67.9 | 72.1 | 41.5 | 33.0 | 69.3 | 54.3 | 60.8 | 49.6 | 62.5 | 73.1 | 63.5 | 58.7 | 58.9 | 61.5 |
| GLiNER-multi v2.1 | 59.9 | 29.6 | 43.0 | 24.0 | 62.6 | 45.7 | 41.9 | 52.4 | 66.7 | 77.4 | 73.5 | 67.2 | 53.7 | 60.9 |
| GLiNER-large v2.1 (EN only) | – | – | – | – | 59.2 | 44.8 | 64.0 | 56.9 | 65.1 | 77.3 | 71.4 | 69.5 | – | 63.5 |
| NuNER-Zero (EN only) | – | – | – | – | 63.7 | 46.5 | 55.5 | 59.8 | 67.3 | 78.5 | 79.8 | 66.7 | – | 64.7 |
| Fine-tuned BERT/RoBERTa (supervised) | 97.5 | 98.7 | 83.9 | 73.0 | 94.3 | 66.7 | 89.2 | – | – | – | – | – | – | – |

### Strict Precision (%)

| Method | MSRA | Resume | CLUENER | Weibo | CoNLL03 | WNUT17 | MIT-Rest | CN-AI | CN-Lit | CN-Music | CN-Pol | CN-Sci |  |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Jev + our pipeline | 84.1 | 89.2 | 65.4 | 46.4 | 82.0 | 50.0 | 71.7 | 73.2 | 76.3 | 81.1 | 84.0 | 80.2 |
| Qwen3.8-27B prompt (API) | 83.9 | 90.2 | 66.2 | 43.7 | 84.5 | 54.8 | 77.8 | 75.3 | 78.6 | 83.3 | 79.2 | 82.9 |
| Qwen3-8B prompt (vLLM, 3090) | 73.8 | 78.1 | 65.4 | 35.8 | 76.2 | 38.2 | 69.3 | 63.2 | 60.5 | 76.4 | 63.3 | 63.6 |
| GLiNER2.5-multi | 60.8 | 65.2 | 46.2 | 37.8 | 67.6 | 50.8 | 52.1 | 46.7 | 59.9 | 66.8 | 57.4 | 56.5 |
| GLiNER-multi v2.1 | 53.0 | 38.5 | 33.9 | 27.6 | 54.4 | 37.4 | 42.4 | 53.8 | 68.6 | 73.6 | 67.4 | 64.1 |
| GLiNER-large v2.1 (EN only) | – | – | – | – | 45.6 | 32.0 | 56.0 | 51.2 | 61.9 | 72.5 | 65.8 | 63.5 |
| NuNER-Zero (EN only) | – | – | – | – | 52.4 | 32.3 | 37.5 | 50.3 | 63.7 | 70.7 | 72.6 | 60.9 |
| Fine-tuned BERT/RoBERTa (supervised) | 96.5 | 95.9 | 69.2 | 61.2 | 92.5 | 72.9 | 80.8 | – | – | – | – | – |

### Strict Recall (%)

| Method | MSRA | Resume | CLUENER | Weibo | CoNLL03 | WNUT17 | MIT-Rest | CN-AI | CN-Lit | CN-Music | CN-Pol | CN-Sci |  |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Jev + our pipeline | 80.2 | 87.5 | 69.8 | 68.5 | 82.0 | 65.3 | 60.1 | 70.7 | 73.4 | 78.7 | 82.4 | 75.5 |
| Qwen3.8-27B prompt (API) | 63.0 | 89.7 | 61.3 | 55.5 | 87.9 | 53.2 | 70.1 | 64.1 | 67.2 | 78.8 | 74.5 | 71.6 |
| Qwen3-8B prompt (vLLM, 3090) | 53.7 | 60.9 | 48.9 | 35.2 | 73.4 | 39.3 | 31.6 | 46.0 | 46.2 | 65.7 | 51.1 | 52.0 |
| GLiNER2.5-multi | 50.6 | 49.3 | 23.4 | 22.1 | 61.6 | 52.0 | 38.2 | 40.3 | 53.4 | 61.6 | 60.0 | 49.1 |
| GLiNER-multi v2.1 | 48.2 | 14.5 | 27.5 | 19.0 | 62.9 | 51.4 | 20.7 | 42.2 | 57.6 | 69.5 | 65.7 | 60.6 |
| GLiNER-large v2.1 (EN only) | – | – | – | – | 63.6 | 51.4 | 40.9 | 48.6 | 58.5 | 70.9 | 62.6 | 66.0 |
| NuNER-Zero (EN only) | – | – | – | – | 67.9 | 58.4 | 34.4 | 51.2 | 57.5 | 69.7 | 72.0 | 60.7 |
| Fine-tuned BERT/RoBERTa (supervised) | 96.9 | 96.2 | 70.5 | 65.7 | 93.4 | 49.7 | 83.1 | – | – | – | – | – |

### Latency per document (seconds, one document at a time)

| Method | MSRA | Resume | CLUENER | Weibo | CoNLL03 | WNUT17 | MIT-Rest | CN-AI | CN-Lit | CN-Music | CN-Pol | CN-Sci | Mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Jev + our pipeline | 0.372 | 0.501 | 0.548 | 0.484 | 0.446 | 0.400 | 0.500 | 0.602 | 0.614 | 0.612 | 0.633 | 0.667 | 0.532 |
| Qwen3.8-27B prompt (API) | 0.958 | 1.593 | 1.390 | 1.216 | 1.210 | 0.993 | 1.252 | 1.644 | 2.115 | 2.611 | 2.675 | 2.132 | 1.649 |
| Qwen3-8B prompt (vLLM, 3090) | 0.470 | 0.869 | 0.820 | 0.969 | 0.523 | 0.409 | 0.414 | 1.275 | 1.671 | 2.230 | 1.856 | 1.683 | 1.099 |
| GLiNER2.5-multi | 0.022 | 0.023 | 0.023 | 0.023 | 0.022 | 0.023 | 0.023 | 0.023 | 0.024 | 0.023 | 0.024 | 0.024 | 0.023 |
| GLiNER-multi v2.1 | 0.021 | 0.018 | 0.018 | 0.019 | 0.018 | 0.018 | 0.018 | 0.018 | 0.019 | 0.019 | 0.019 | 0.019 | 0.019 |
| GLiNER-large v2.1 (EN only) | – | – | – | – | 0.033 | 0.032 | 0.033 | 0.034 | 0.034 | 0.033 | 0.033 | 0.033 | 0.033 |
| NuNER-Zero (EN only) | – | – | – | – | 0.035 | 0.032 | 0.033 | 0.033 | 0.037 | 0.033 | 0.033 | 0.033 | 0.034 |
| Fine-tuned BERT/RoBERTa (supervised) | 0.008 | 0.013 | 0.007 | 0.008 | 0.006 | 0.012 | 0.011 | – | – | – | – | – | 0.009 |

### Cost per 1,000 documents (USD)

| Method | MSRA | Resume | CLUENER | Weibo | CoNLL03 | WNUT17 | MIT-Rest | CN-AI | CN-Lit | CN-Music | CN-Pol | CN-Sci | Mean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Jev + our pipeline | 0.365 | 0.537 | 0.849 | 0.744 | 0.191 | 0.205 | 0.206 | 0.713 | 0.893 | 1.079 | 0.939 | 0.990 | 0.642 |
| Qwen3.8-27B prompt (API) | 0.169 | 0.308 | 0.286 | 0.201 | 0.187 | 0.146 | 0.174 | 0.285 | 0.351 | 0.428 | 0.381 | 0.391 | 0.275 |
| Qwen3-8B prompt (vLLM, 3090) | 0.0020 | 0.0046 | 0.0022 | 0.0032 | 0.0028 | 0.0019 | 0.0019 | 0.0036 | 0.0041 | 0.0049 | 0.0053 | 0.0061 | 0.0036 |
| GLiNER2.5-multi | 0.0014 | 0.0014 | 0.0014 | 0.0014 | 0.0014 | 0.0014 | 0.0014 | 0.0014 | 0.0014 | 0.0014 | 0.0014 | 0.0014 | 0.0014 |
| GLiNER-multi v2.1 | 0.0013 | 0.0011 | 0.0011 | 0.0012 | 0.0011 | 0.0011 | 0.0011 | 0.0011 | 0.0012 | 0.0012 | 0.0012 | 0.0012 | 0.0012 |
| GLiNER-large v2.1 (EN only) | – | – | – | – | 0.0020 | 0.0019 | 0.0020 | 0.0021 | 0.0021 | 0.0020 | 0.0020 | 0.0020 | 0.0020 |
| NuNER-Zero (EN only) | – | – | – | – | 0.0022 | 0.0020 | 0.0020 | 0.0020 | 0.0023 | 0.0020 | 0.0020 | 0.0020 | 0.0021 |
| Fine-tuned BERT/RoBERTa (supervised) | 0.0005 | 0.0008 | 0.0004 | 0.0005 | 0.0004 | 0.0007 | 0.0007 | – | – | – | – | – | 0.0006 |

### Resources and prerequisites

| Method | Parameters | Disk | Peak GPU memory | Runs on | Needs labelled training data | What you provide per task |
|---|---|---|---|---|---|---|
| Jev + our pipeline | – | – | none (HTTPS client) | Jev API | no | type name + 1-line description |
| Qwen3.8-27B prompt (API) | 27B | – | none (HTTPS client) | DashScope API | no | same prompt / descriptions |
| Qwen3-8B prompt (vLLM, 3090) | 8.2B | 15.3 GB | ~21 GB (vLLM pre-allocates 90%) | RTX 3090 24 GB | no | same prompt / descriptions |
| GLiNER2.5-multi | ~0.29B | 1.1 GB | 2.8 GB | RTX 3090 (or CPU) | no | label + description |
| GLiNER-multi v2.1 | ~0.3B | 2.2 GB | 2.4 GB | RTX 3090 (or CPU) | no | label names |
| GLiNER-large v2.1 (EN only) | ~0.46B | 1.7 GB | 2.8 GB | RTX 3090 (or CPU) | no | label names |
| NuNER-Zero (EN only) | ~0.45B | 3.3 GB | 3.3 GB | RTX 3090 (or CPU) | no | label names |
| Fine-tuned BERT/RoBERTa (supervised) | 0.1–0.36B | 0.4–1.3 GB | 0.4–1.7 GB | RTX 3090 (or CPU) | yes: 1.4k–45k labelled sentences per dataset | one model per dataset |

### Measurement notes

- Accuracy: 200 test sentences per dataset (fixed seed), CLUENER dev as test; same sentences for every method.
- Jev latency / cost: 30 test sentences per dataset, no cache, one document at a time.
- Hosted LLMs (DashScope): same prompt and type descriptions as Jev, JSON output, thinking disabled where the model allows it; latency per request at 8 concurrent requests ; cost from returned token counts at Beijing list price.
- Local LLMs (vLLM on RTX 3090, JSON-constrained decoding, temperature 0): latency = one request at a time; cost from batched throughput at the rental price.
- Local encoders: batch size 1 on RTX 3090; cost = latency × $0.22/h (an upper bound; batching is cheaper).
