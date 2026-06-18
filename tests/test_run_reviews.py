from scripts.run_reviews import infer_language, output_name_for_diff


def test_infer_language_from_assignment_diff_names():
    assert infer_language("diff1_python.txt") == "python"
    assert infer_language("diff2_javascript.txt") == "javascript"
    assert infer_language("diff3_typescript.txt") == "typescript"


def test_output_name_matches_submission_contract():
    assert output_name_for_diff("diff1_python.txt") == "diff1_review.json"
    assert output_name_for_diff("diff2_javascript.txt") == "diff2_review.json"
    assert output_name_for_diff("diff3_typescript.txt") == "diff3_review.json"


def test_infer_language_from_common_extensions_for_future_diffs():
    assert infer_language("new_auth.py.diff") == "python"
    assert infer_language("bulk-user-controller.js.patch") == "javascript"
    assert infer_language("order-service.ts.diff") == "typescript"
