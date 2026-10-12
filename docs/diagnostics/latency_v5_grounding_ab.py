"""Alternating single-thread CPU intervention, frozen source versus candidate.

No source replacement, changed thresholds, providers, caches or HTTP SLO claim.
"""
import json
from pathlib import Path
import subprocess
import sys
import time
import types
from kernel.core import grounding
from kernel.sidecar.ingestor import IngestorImpl
from packs.memo.pack import ClassifiedMemoPack

BASE = 'e2b9d4236fc067241318b5ed56f5c4f495761c41'
source = subprocess.check_output(['git', 'show', f'{BASE}:kernel/core/grounding.py'], text=True)
baseline = types.ModuleType('frozen_baseline_grounding')
exec(compile(source, 'frozen_baseline_grounding.py', 'exec'), baseline.__dict__)
chunks, _, _ = IngestorImpl().ingest('fixtures/wedge/sample_memo_01.txt')
fields = ClassifiedMemoPack().extract(chunks)
def run(module):
    verifier = module.GroundingVerifierImpl()
    return [verifier.verify(ext.value, ext.source_span, chunks) for ext in fields]
expected = run(baseline)
assert run(grounding) == expected, 'Method/span/page/bbox mismatch on real memo'
rows = []
for pair in range(3):
    for name, module in [('baseline', baseline), ('candidate', grounding)]:
        began, cpu = time.perf_counter(), time.thread_time()
        observed = run(module)
        rows.append(dict(pair=pair, variant=name, fields=len(fields),
                         thread_cpu_ms=(time.thread_time()-cpu)*1000,
                         wall_ms=(time.perf_counter()-began)*1000))
        assert observed == expected
out = dict(scope='six alternating single-thread real memo grounding runs, no SQLite/HTTP/parser timing',
           baseline_commit=BASE, candidate_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
           methods=[method.value for method, _ in expected], rows=rows)
Path(sys.argv[1]).write_text(json.dumps(out, indent=2))
print('Exact real memo equivalence;', len(rows), 'bounded runs saved')
