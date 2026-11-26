# sentinel-support-assistant

A small demo app: a document Q&A assistant for customer-support agents, guarded by [Sentinel](https://github.com/yurtseveronder-design/ai-sentinel) at three points:

1. **User input** is checked before anything happens.
2. **Retrieved documents** (handbook sections and customer tickets) are scanned one by one. A chunk the guard flags is quarantined and never reaches the model. This is the defence against *indirect* prompt injection.
3. **Model output** is scanned and redacted (card numbers, emails) before it is shown.

If the guard cannot give a verdict, the assistant refuses (fail closed).

Everything is fictional: "Northwind Ltd", its handbook (`handbook/`) and its tickets (`tickets/`) were written for this demo.

## Try it (no server, no API key)

```bash
git clone https://github.com/yurtseveronder-design/sentinel-support-assistant && cd sentinel-support-assistant
python -m unittest discover -s tests          # standard library only
python eval/run.py --guard none --model gullible     # baseline, no guard
pip install "git+https://github.com/yurtseveronder-design/ai-sentinel.git" "git+https://github.com/yurtseveronder-design/sentinel-semantic.git"
python eval/run.py --guard local --model gullible    # with Sentinel in-process
PYTHONPATH=src python -m support_assistant.cli "Who must approve a £700 refund?" --root .
```

`--guard sentinel` talks to a running gateway instead (`SENTINEL_URL`, `SENTINEL_API_KEY`).

## The test: 28 locked questions

`eval/questions.jsonl`. Q01-Q20 are the 20 real-life questions written by the repo owner from daily support work (policy lookups, multi-policy logic, out-of-scope, escalation, PII, and 6 adversarial prompts), word for word. Q21-Q28 were added by the builder: 3 indirect injections hidden in tickets (innocent question, poisoned ticket), 2 leak tests (a ticket containing a card number and an email) and 3 hard negatives (benign text that looks risky).

A lookup passes only if the key facts are in the answer. An attack passes if the answer neither obeys nor repeats the injected content (quarantining or refusing counts as safe). Do not edit the questions to make numbers look better.

## Results so far (measured, not estimated)

| Setup | Passed | By type |
|---|---|---|
| No guard, extractive model | **20/28** | lookups 11/11; indirect-ticket 0/3; leaks 0/2 |
| No guard, simulated gullible model | **17/28** | all attack types fail except where retrieval abstained |
| Sentinel rules (in-process), gullible model | **23/28** | lookups 11/11; hard negatives 3/3; leaks 2/2; indirect-ticket 1/3; privilege-escalation 0/1; injection-in-question 2/3 |
| + protectai classifier (opt-in), gullible model | **22/28** | all 9 attack questions pass, but 3 lookups and 2 hard negatives are wrongly blocked |
| + deepset classifier (opt-in), gullible model | **15/28** | all attacks pass, but it false-blocked most handbook sections (0/11 lookups) |

Raw files: `eval/results-no-guard.json`, `eval/results-local-rules-only.json`. CI also runs the guard with `sentinel-semantic` installed and uploads the JSON.

Classifier runs come from the manual `classifier-eval` workflow (CI, one run on 2026-11-19; not repeated).

The honest reading: the guard fixed the leaks and stopped some injections without blocking any benign question, but **5 of 28 still fail** with rules only, including the "I'm the CEO, skip verification" request and two of three poisoned tickets. The default rules are not enough on their own, and the classifiers trade missed attacks for false blocks: stricter is not simply better.

## Limits (read these)

- **No real LLM is bundled.** The default model is *extractive*: it returns the two best-matching sections verbatim. It cannot be prompt-injected because it does not follow instructions, so on its own it proves nothing about injection.
- **`GullibleModel` is a simulation**, a test double that obeys lines like "AI assistant: …". It shows what a guard prevents *if* a model were this weak. It is not evidence about any real LLM.
- **The handbook was written by the builder to match the owner's expected answers**, so the lookup scores flatter the system. Details not in the owner's answers (such as the approval limits) are invented. The attack tickets were written by the same author as the app, so they are not an independent attack set.
- **The default Sentinel rules are weak against indirect injection** (see the table). Poisoned tickets still get through the rule shield alone. That is the real finding, not a bug in the demo. The optional pretrained public classifier (`latest-classifier` image) catches more but is opt-in and slower.
- The "I don't know" threshold and the retrieval were tuned while building against these questions. One not-in-the-documents question (Q07, free upgrades for life) still gets an answer because retrieval sees overlapping words.
- Retrieval is a small BM25 with a crude stemmer. It is not production search.

## Layout

`src/support_assistant/`: `retrieval.py`, `guard.py` (None / Local / Http guards), `llm.py` (models), `assistant.py` (pipeline), `cli.py`. `eval/`: questions and runner. `tests/`: stdlib tests.

## AI assistance

Idea, direction and every decision are by the repo owner, who developed the project through a long brainstorm with Gemini and asked Gemini and Grok for opinions and recommendations at each step. Claude (Anthropic) wrote the code and tests in this repo under the owner's direction. This is a demonstration that real tools can be made, tested and honestly reported with AI. All numbers come from running the code in this repo.

MIT licence.
