from infravox_reviewer.diff_parser import extract_added_lines
from infravox_reviewer.reviewers import (
    correctness_reviewer,
    performance_reviewer,
    security_reviewer,
    style_reviewer,
    test_coverage_reviewer,
)


def _titles(findings):
    return {finding.title for finding in findings}


def test_security_reviewer_detects_generic_sql_injection_and_hardcoded_secret():
    diff = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -20,0 +21,4 @@
+def find_account(account_id):
+    sql = "SELECT * FROM accounts WHERE id = " + account_id
+    return db.execute(sql)
+GITHUB_TOKEN = "github-token-placeholder-value"
"""

    findings = security_reviewer(extract_added_lines(diff), "python")

    titles = _titles(findings)
    assert "Dynamic SQL construction can allow injection" in titles
    assert "Hardcoded secret value" in titles


def test_security_reviewer_detects_generic_javascript_template_sql_and_password_hashing():
    diff = """diff --git a/controller.js b/controller.js
--- a/controller.js
+++ b/controller.js
@@ -1,0 +1,5 @@
+async function login(req, res) {
+  const sql = `SELECT * FROM users WHERE email = '${req.body.email}'`;
+  await db.query('UPDATE users SET password = ?', [req.body.password]);
+  res.json({ ok: true });
+}
"""

    findings = security_reviewer(extract_added_lines(diff), "javascript")

    titles = _titles(findings)
    assert "Dynamic SQL construction can allow injection" in titles
    assert "Password update stores un-hashed password input" in titles


def test_security_reviewer_anchors_authorization_gap_to_sensitive_function():
    diff = """diff --git a/controller.js b/controller.js
--- a/controller.js
+++ b/controller.js
@@ -1,0 +1,8 @@
+// PR: add password reset
+
+async function resetPassword(req, res) {
+  const { email, newPassword } = req.body;
+  await db.query('UPDATE users SET password = ? WHERE email = ?', [newPassword, email]);
+  res.json({ ok: true });
+}
"""

    findings = security_reviewer(extract_added_lines(diff), "javascript")

    auth_finding = next(
        finding
        for finding in findings
        if finding.title == "Authorization check missing for sensitive operation"
    )
    assert auth_finding.line == 3


def test_correctness_reviewer_detects_generic_missing_null_check_and_unvalidated_json():
    diff = """diff --git a/orders.py b/orders.py
--- a/orders.py
+++ b/orders.py
@@ -1,0 +1,5 @@
+def handler():
+    data = request.json
+    order = repo.find(data["order_id"])
+    order.status = "cancelled"
+    return {"ok": True}
"""

    findings = correctness_reviewer(extract_added_lines(diff), "python")

    titles = _titles(findings)
    assert "Request JSON is used without validation" in titles
    assert "Possible null dereference after lookup" in titles


def test_correctness_reviewer_detects_const_await_lookup_without_guard():
    diff = """diff --git a/orders.ts b/orders.ts
--- a/orders.ts
+++ b/orders.ts
@@ -1,0 +1,5 @@
+export async function cancelOrder(orderId: string) {
+  const order = await orderRepo.findById(orderId);
+  order.status = 'cancelled';
+  await orderRepo.save(order);
+}
"""

    findings = correctness_reviewer(extract_added_lines(diff), "typescript")

    assert "Possible null dereference after lookup" in _titles(findings)


def test_correctness_reviewer_does_not_duplicate_missing_array_result_as_null_deref():
    diff = """diff --git a/users.js b/users.js
--- a/users.js
+++ b/users.js
@@ -1,0 +1,6 @@
+async function getUsers(ids) {
+  const users = [];
+  const user = await db.query('SELECT * FROM users WHERE id = ?', [ids[0]]);
+  users.push(user[0]);
+  return users;
+}
"""

    findings = correctness_reviewer(extract_added_lines(diff), "javascript")

    titles = _titles(findings)
    assert "Missing result handling" in titles
    assert "Possible null dereference after lookup" not in titles


def test_correctness_reviewer_does_not_flag_query_array_map_as_null_deref():
    diff = """diff --git a/activity.js b/activity.js
--- a/activity.js
+++ b/activity.js
@@ -1,0 +1,6 @@
+async function getActivity(userId) {
+  const logs = await db.query('SELECT * FROM activity_logs WHERE user_id = ?', [userId]);
+  const enriched = logs.map(log => ({ ...log }));
+  return enriched;
+}
"""

    findings = correctness_reviewer(extract_added_lines(diff), "javascript")

    assert "Possible null dereference after lookup" not in _titles(findings)


def test_performance_reviewer_detects_generic_await_in_loop_and_unbounded_polling():
    diff = """diff --git a/jobs.ts b/jobs.ts
--- a/jobs.ts
+++ b/jobs.ts
@@ -1,0 +1,8 @@
+export async function run(ids: string[]) {
+  for (const id of ids) {
+    await worker.run(id);
+  }
+  while (status === 'pending') {
+    await sleep(1000);
+  }
+}
"""

    findings = performance_reviewer(extract_added_lines(diff), "typescript")

    titles = _titles(findings)
    assert "Await inside loop serializes independent work" in titles
    assert "Unbounded polling loop" in titles


def test_performance_reviewer_detects_undefined_related_record_enrichment_lookup():
    diff = """diff --git a/report.ts b/report.ts
--- a/report.ts
+++ b/report.ts
@@ -1,0 +1,8 @@
+export async function listInvoices() {
+  const invoices = await invoiceRepo.findRecent();
+  const enriched = invoices.map(invoice => {
+    return { ...invoice, account: accounts[invoice.accountId] };
+  });
+  return enriched;
+}
"""

    findings = performance_reviewer(extract_added_lines(diff), "typescript")

    assert "Undefined related-record lookup in enrichment" in _titles(findings)


def test_style_reviewer_detects_any_outside_sample_fixture():
    diff = """diff --git a/types.ts b/types.ts
--- a/types.ts
+++ b/types.ts
@@ -1,0 +1,2 @@
+const payload: any = getPayload();
+console.log(payload);
"""

    findings = style_reviewer(extract_added_lines(diff), "typescript")

    assert "Avoid any for newly added value" in _titles(findings)


def test_test_coverage_reviewer_detects_state_transition_side_effect_without_tests():
    diff = """diff --git a/shipping.ts b/shipping.ts
--- a/shipping.ts
+++ b/shipping.ts
@@ -1,0 +1,7 @@
+// PR: cancel shipped orders
+export async function shipOrder(orderId: string) {
+  const order = await orderRepo.findById(orderId);
+  order.status = 'shipped';
+  await orderRepo.save(order);
+  await emailClient.send(order.customerEmail, 'Order shipped');
+}
"""

    findings = test_coverage_reviewer(extract_added_lines(diff), "typescript")

    coverage_finding = next(
        finding
        for finding in findings
        if finding.title == "State transition side effects need tests"
    )
    assert coverage_finding.line == 4
