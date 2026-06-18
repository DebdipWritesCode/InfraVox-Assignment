from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx


CONTEXT_BY_DIFF = {
    "diff1_python.txt": "Add refund endpoint and fix transaction lookup",
    "diff2_javascript.txt": "Add bulk user fetch and fix password reset",
    "diff3_typescript.txt": "Add order cancellation and status polling",
}


def infer_language(filename: str) -> str:
    lowered = filename.lower()
    if "python" in lowered:
        return "python"
    if "javascript" in lowered:
        return "javascript"
    if "typescript" in lowered:
        return "typescript"
    if lowered.endswith((".py", ".py.diff", ".py.patch")):
        return "python"
    if lowered.endswith((".js", ".jsx", ".js.diff", ".js.patch", ".jsx.diff", ".jsx.patch")):
        return "javascript"
    if lowered.endswith((".ts", ".tsx", ".ts.diff", ".ts.patch", ".tsx.diff", ".tsx.patch")):
        return "typescript"
    raise ValueError(f"Cannot infer language from {filename!r}")


def output_name_for_diff(filename: str) -> str:
    prefix = filename.split("_", 1)[0]
    return f"{prefix}_review.json"


def review_diff(client: httpx.Client, base_url: str, diff_path: Path) -> dict:
    response = client.post(
        f"{base_url.rstrip('/')}/review",
        json={
            "diff": diff_path.read_text(encoding="utf-8"),
            "language": infer_language(diff_path.name),
            "context": CONTEXT_BY_DIFF.get(diff_path.name),
        },
    )
    response.raise_for_status()
    return response.json()


def run_all(base_url: str, diffs_dir: Path, reviews_dir: Path) -> list[Path]:
    reviews_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    diff_paths = sorted(
        path
        for pattern in ("diff*.txt", "*.diff", "*.patch")
        for path in diffs_dir.glob(pattern)
        if path.is_file()
    )
    with httpx.Client(timeout=60) as client:
        for diff_path in diff_paths:
            report = review_diff(client, base_url, diff_path)
            output_path = reviews_dir / output_name_for_diff(diff_path.name)
            output_path.write_text(
                json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            written.append(output_path)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Run InfraVox assignment reviews.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--diffs-dir", type=Path, default=Path("diffs"))
    parser.add_argument("--reviews-dir", type=Path, default=Path("reviews"))
    args = parser.parse_args()

    written = run_all(args.base_url, args.diffs_dir, args.reviews_dir)
    for path in written:
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
