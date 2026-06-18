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

The deterministic reviewers work without an API key, which keeps local tests and the provided assignment diffs reproducible. When `GROQ_API_KEY` is present, the project is ready for Groq/LangChain augmentation and `/health` reports that connectivity can be checked. The default model is `llama-3.1-8b-instant`, Groq's current replacement for the assignment brief's deprecated `llama3-8b-8192` model.

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

The core pipeline is a LangGraph `StateGraph`:

```text
START -> parse_diff
parse_diff -> security_reviewer
parse_diff -> performance_reviewer
parse_diff -> correctness_reviewer
parse_diff -> style_reviewer
parse_diff -> test_coverage_reviewer
all reviewers -> merge_findings -> END
```

Each specialist reviewer produces structured `Finding` objects. The merge node deduplicates findings, assigns stable IDs, computes severity and verdict, and emits the exact `ReviewReport` contract from the assignment.

## Future Diff Support

The reviewer does not hand-edit or hardcode the generated JSON files. The baseline review layer uses generalized deterministic patterns for common review issues, including dynamic SQL construction, hardcoded secrets, plaintext password updates, unvalidated request JSON, missing lookup null checks, unbounded polling, `await` inside loops, and unsafe TypeScript `any`.

The three provided assignment diffs remain covered by tests, but future diffs can also be added to `diffs/` as `*.diff`, `*.patch`, or assignment-style `diff*.txt` files. `scripts/run_reviews.py` infers language from assignment filenames or common extensions such as `.py.diff`, `.js.patch`, and `.ts.diff`.

Groq is available for future enrichment and health checks, but deterministic checks are the reliable baseline so the assignment artifacts remain reproducible.

The part I am happiest with is the hybrid shape: deterministic rules make the planted-bug evaluation reliable, while the LangGraph agent boundaries keep the system easy to extend for Groq-powered review of new diffs. With one more day, I would add a stronger strict-JSON LLM enrichment pass and golden-file evaluations for a fourth unseen diff.
