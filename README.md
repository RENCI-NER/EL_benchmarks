# EL_benchmarks

Benchmarks for evaluating biomedical entity linking: a mention in text → a Babel/NodeNorm identifier. Named-entity recognition is out of scope; mentions come with the benchmark.

Datasets are meant to be static: each one is built by a documented script from a named source, and the built files are committed.

| Directory | What it is | Status |
|---|---|---|
| [`medmentions_assessed/`](medmentions_assessed/) | MedMentions mentions whose proposed links (from MedMentions, gpt-oss, o3-mini) were judged by two people in bagel-eval, plus adjudication of their disagreements | built: 1,517 mentions, 2,041 judgments |
| [`craft/`](craft/) | The CRAFT corpus concept annotations, adapted to Babel | planned |

```bash
uv sync
uv run pytest
```
