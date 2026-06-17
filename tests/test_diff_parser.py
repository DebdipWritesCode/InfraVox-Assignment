from infravox_reviewer.diff_parser import extract_added_lines


def test_extract_added_lines_skips_diff_metadata_and_counts_added_code_lines():
    diff = """# sample.py
+ def first():
+     return 1
 context line
+ API_KEY = 'secret'
"""

    lines = extract_added_lines(diff)

    assert [line.number for line in lines] == [1, 2, 3]
    assert lines[0].content == "def first():"
    assert lines[2].content == "API_KEY = 'secret'"


def test_extract_added_lines_preserves_assignment_line_numbers():
    diff = """# payments_service.py

+ def get_transaction(user_id, transaction_id):
+     query = f"SELECT * FROM transactions WHERE user_id = {user_id}"
+     query += f" AND transaction_id = {transaction_id}"
"""

    lines = extract_added_lines(diff)

    assert lines[0].number == 1
    assert lines[1].number == 2
    assert lines[2].number == 3


def test_extract_added_lines_uses_new_file_hunk_line_numbers_and_file_path():
    diff = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -8,2 +10,4 @@ def handler():
 context = 1
+password = request.json["password"]
+query = "SELECT * FROM users WHERE name = " + name
 unchanged = True
+return query
"""

    lines = extract_added_lines(diff)

    assert [(line.number, line.file_path, line.content) for line in lines] == [
        (11, "app.py", 'password = request.json["password"]'),
        (12, "app.py", 'query = "SELECT * FROM users WHERE name = " + name'),
        (14, "app.py", "return query"),
    ]
