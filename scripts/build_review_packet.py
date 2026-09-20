#!/usr/bin/env python3
"""Generate the maintainer review packet from cases plus curated challenge notes."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "suites/php-web-v0.1/cases"
OUT = ROOT / "docs/HUMAN_REVIEW_PACKET.md"

CHALLENGES = {
"laravel-authz-001": ("Policy existence, registration and authenticated-only route make the missing object authorization decidable.", "UpdatePostRequest could authorize, but the supplied context makes the policy call the stated control.", "No second defect: validated input and route behaviour are unchanged."),
"laravel-authz-002": ("The context excludes controller checks and other middleware.", "A deployment-level gate could protect the routes, but it is explicitly outside the supplied facts.", "All three exposed routes are one removed middleware-boundary defect."),
"laravel-clean-001": ("The policy call remains and the two literal fields are explicitly fillable.", "A reviewer may treat fill() as mass assignment regardless of its literal input.", "No accidental defect; formatting and save semantics remain equivalent."),
"laravel-ghsa-debug-xss-001": ("The context pins attacker-controlled HTML, a reachable HTML response and no later mitigation.", "A locked-down debug endpoint would lower exploitability, but reachability is supplied.", "No separate information-disclosure label; diagnostics exposure is a stated precondition."),
"laravel-ghsa-env-001": ("The context pins CGI argv as request-controlled and the return value as configuration selection.", "Some deployments do not populate web argv; this fixture explicitly does.", "Do not infer RCE, debug exposure or .env loading; none is supplied."),
"laravel-ghsa-env-clean-001": ("The early non-CLI return prevents web input from reaching the option scan.", "A reviewer may flag returning argv-derived values without noticing it occurs only for operator-controlled CLI.", "Empty CLI values are pre-existing behaviour, not a new web defect."),
"laravel-injection-001": ("Unvalidated request input is visibly concatenated into executable SQL.", "A database allow-list could mitigate it, but the context excludes one.", "No output sink or authorization change supplies a second defect."),
"laravel-xss-001": ("Free-text user content moves from escaped to raw Blade output with no sanitizer.", "Trusted markup would make raw output intentional, but context says any registered user supplies unsanitized text.", "Author name remains escaped; only the body sink changes."),
"php-clean-001": ("The same named PDO parameter remains bound and LIMIT 1 matches the single-row API.", "A reviewer may flag SQL because the query text changed.", "No concatenation or changed trust boundary exists."),
"php-injection-001": ("Raw GET input is visibly concatenated after removal of the prepared statement.", "Input validation could constrain it, but the context excludes filtering.", "HTML output is still escaped, so XSS is not a second defect."),
"php-secrets-001": ("A key-shaped literal is introduced in a tracked deployed file.", "The literal is fabricated, but committing credential material is the behaviour under test.", "The example endpoint and timeout do not introduce another defect."),
"wp-authz-001": ("The hook admits any logged-in user and context excludes a shared permission wrapper.", "A nonce may look like authorization, but it verifies intent rather than capability.", "Prepared SQL and integer coercion exclude injection; nonce excludes the intended CSRF finding."),
"wp-clean-001": ("Nonce, capability gate, typed database formats and JSON serialization all remain.", "A reviewer may demand HTML escaping for a value returned as JSON.", "Direct $_POST access is pre-existing; the change adds sanitization."),
"wp-deser-001": ("An unsigned attacker-controlled cookie reaches unserialize with gadget classes available.", "allowed_classes=false could narrow object injection, but it is not used.", "The array fallback is post-deserialization and does not prevent gadget execution."),
"wp-xss-001": ("Attacker-controlled query input replaces esc_html in a public HTML sink.", "A global escaping layer could mitigate it, but context excludes one.", "Result titles remain escaped; only the query reflection is defective."),
}

def main():
    lines = ["# Human review packet — `php-web-v0.1`", "",
        "> **Decision record:** Oleksii Siniaiev explicitly accepted all fifteen cases on 2026-09-20. The cases are frozen in suite revision 0.1.2. The original agent recommendations remain below for audit history; `academic_review` is false because no separate review by Valeriia Chumak was confirmed.", "",
        "The displayed context and diff are exactly what the evaluated model receives inside the versioned reviewer prompt.", ""]
    for path in sorted(CASES.glob("*.json")):
        c = json.loads(path.read_text())
        finding = c["expected_findings"][0] if c["expected_findings"] else None
        decidable, alternative, second = CHALLENGES[c["id"]]
        provenance = "Original synthetic fixture."
        if c["source_type"] == "public_advisory":
            provenance = (f"Advisory-derived synthetic reconstruction of `{c['advisory_id']}` for "
                          f"{c['original_project']}; not upstream code or an upstream patch. Source: {c['source_url']}")
        expected = "**CLEAN** (no expected findings)" if not finding else (
            f"`{finding['defect_type']}` / **{finding['severity']}** — {finding['description']}")
        lines += [f"## {c['id']}", "", f"- **Source / ecosystem / category:** `{c['source_type']}` / `{c['ecosystem']}` / `{c['category']}`",
            f"- **Expected:** {expected}", f"- **Decidable because:** {decidable}",
            f"- **Plausible alternative:** {alternative}",
            f"- **Second-defect check:** {second}"]
        if c["is_clean"]:
            lines += [f"- **Strongest false-alarm temptation:** {alternative}"]
        lines += [f"- **Provenance:** {provenance}", "- **Agent recommendation:** **ACCEPT**", "",
            f"**Supplied description:** {c['description']}", "", f"**Supplied context:** {c['context']}", "",
            "```diff", c["diff"].rstrip(), "```", ""]
    OUT.write_text("\n".join(lines) + "\n")

if __name__ == "__main__":
    main()
