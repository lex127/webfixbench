# Security policy

WebFixBench is a defensive research benchmark. Please report vulnerabilities in
the harness privately through GitHub's **Security → Report a vulnerability**
flow. Do not open a public issue containing credentials, private code, an
unpublished vulnerability, or working exploit material.

The synthetic benchmark fixtures are intentionally public and are not security
reports. Hosted-model credentials remain the operator's responsibility; use
scoped secrets, never commit `.env`, and rotate a key if it appears in logs or
artifacts.

Only the current default branch is maintained. We will acknowledge a complete
report when maintainer capacity permits and coordinate disclosure for confirmed
issues. This project does not accept client code, zero-days or live-target data.
