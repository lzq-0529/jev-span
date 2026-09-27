"""Parameter count and peak GPU memory of each local baseline while running 50 test documents."""
import json, sys, time
from pathlib import Path
import torch
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import baselines_gpu as B

JOBS = [
    ("finetuned", "msra"), ("finetuned", "conll"), ("finetuned", "wnut"),
    ("gliner_multi", "crossner_politics"), ("gliner_large", "crossner_politics"),
    ("nuner_zero", "crossner_politics"), ("gliner2.5", "crossner_politics"),
]
out = {}
for method, name in JOBS:
    torch.cuda.empty_cache(); torch.cuda.reset_peak_memory_stats()
    items = B.load_items(name)[:50]
    if method == "finetuned":
        model_id, predict = B.run_finetuned(name, items, "cuda")
    elif method == "gliner2.5":
        model_id, predict = B.run_gliner2(name, "cuda")
    else:
        mid = {"gliner_multi": "urchade/gliner_multi-v2.1", "gliner_large": "urchade/gliner_large-v2.1", "nuner_zero": "numind/NuNER_Zero"}[method]
        model_id, predict = B.run_gliner(name, mid, "cuda")
    for it in items:
        predict(it["text"])
    torch.cuda.synchronize()
    params = None
    for obj in list(globals().values()):
        pass
    peak = torch.cuda.max_memory_allocated() / 2**30
    out[f"{method}:{model_id}"] = {"peak_gpu_gb": round(peak, 2)}
    print(method, model_id, f"peak {peak:.2f} GB", flush=True)
(HERE / "results" / "gpu" / "resources.json").write_text(json.dumps(out, indent=2))
