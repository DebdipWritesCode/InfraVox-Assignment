# InfraVox AI Code Reviewer

Assignment A implementation: a FastAPI service with a LangGraph review pipeline that accepts raw PR diffs and returns structured, line-level code reviews across security, performance, correctness, style, and test coverage.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn infravox_reviewer.main:app --reload
```

Add your Groq key to `.env` before live LLM-backed testing:

```dotenv
GROQ_API_KEY=your_groq_api_key_here
```

The deterministic fallback checks work without an API key, which keeps local tests and the provided assignment diffs reproducible. When `GROQ_API_KEY` is present and `ENABLE_LLM_REVIEW=true`, each of the five specialist reviewer agents calls Groq through LangChain. The default model is `llama-3.1-8b-instant`, Groq's current replacement for the assignment brief's deprecated `llama3-8b-8192` model.

## API

```bash
curl -X POST http://127.0.0.1:8000/review \
  -H "Content-Type: application/json" \
  -d '{"diff":"+ def example():\n+     return 1","language":"python"}'
```

Endpoints:

- `POST /review` creates a review, stores it in memory, returns a `ReviewReport`, and exposes the generated review ID in the `X-Review-ID` response header.
- `GET /review/{review_id}` retrieves a stored review.
- `GET /reviews` lists generated reviews for this process.
- `GET /health` reports service and Groq configuration status.

## Ways to Run Reviews

There are two supported ways to run the reviewer:

- **Submission script:** runs every local diff file through the FastAPI API and writes JSON files to `reviews/`.
- **Streamlit demo UI:** gives a polished browser view for live walkthroughs and screen recording.

### Submission Script

With the API server running:

```bash
python scripts/run_reviews.py \
  --base-url http://127.0.0.1:8000 \
  --diffs-dir diffs \
  --reviews-dir reviews
```

That reads all supported local diff files from `diffs/` (`diff*.txt`, `*.diff`, `*.patch`), posts each one to `POST /review`, and writes the returned `ReviewReport` JSON files into `reviews/`. For the assignment ZIP, this produces:

- `reviews/diff1_review.json`
- `reviews/diff2_review.json`
- `reviews/diff3_review.json`

## Streamlit Demo UI

For the screen recording, run the FastAPI service in one terminal:

```bash
uvicorn infravox_reviewer.main:app --reload
```

Then run the optional Streamlit demo in another terminal:

```bash
streamlit run streamlit_app.py
```

The Streamlit UI reads the local `diffs/` files, posts the selected diff to `POST /review`, and renders the returned `ReviewReport` as a summary, finding-count metrics, a doc-style findings table, missing-test suggestions, and raw JSON.

## Architecture

The core pipeline is a LangGraph `StateGraph` that parses the diff once, fans out to five
specialist reviewer agents, then merges their structured findings:

```text
START -> parse_diff
parse_diff -> security_reviewer
parse_diff -> performance_reviewer
parse_diff -> correctness_reviewer
parse_diff -> style_reviewer
parse_diff -> test_coverage_reviewer
all specialist reviewers -> merge_findings -> END
```

Each specialist reviewer is an AI agent with a category-specific Groq prompt. Inside each
reviewer node, a deterministic rules layer first produces seed findings for that category.
Those seed findings are included in the Groq prompt so the LLM can validate them and add
additional high-confidence findings. If Groq is disabled, unavailable, or returns no valid
structured findings while the rules layer found issues, the deterministic findings are used as
the fallback output.

Before sending a prompt to Groq, the prompt builder redacts common secret-like tokens such as
Stripe, Groq, GitHub, and Slack token prefixes. The merge node deduplicates findings, assigns
stable IDs, computes severity and verdict, and emits the exact `ReviewReport` contract from the
assignment.

## Future Diff Support

The reviewer does not hand-edit or hardcode the generated JSON files. The baseline review layer uses generalized deterministic patterns for common review issues, including dynamic SQL construction, hardcoded secrets, plaintext password updates, unvalidated request JSON, missing lookup null checks, unbounded polling, `await` inside loops, and unsafe TypeScript `any`.

The three provided assignment diffs remain covered by tests, but future diffs can also be added to `diffs/` as `*.diff`, `*.patch`, or assignment-style `diff*.txt` files. `scripts/run_reviews.py` infers language from assignment filenames or common extensions such as `.py.diff`, `.js.patch`, and `.ts.diff`.

Groq is used inside the five specialist reviewer agents when configured, while deterministic checks remain the fallback layer so assignment artifacts and automated tests stay reproducible.

The part I am happiest with is the hybrid shape: the five LangGraph reviewer agents are Groq-backed for the live AI review, while deterministic fallback checks protect planted-bug recall and make local testing reliable. With one more day, I would make the rules engine tighter by adding more checks, edge cases, and language-specific patterns for unseen diffs.
