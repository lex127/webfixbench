# WebFixBench landing page

Static, dependency-free landing page for WebFixBench.

## Local preview

From the repository root:

```bash
python -m http.server 8000 --directory site
```

Then open <http://localhost:8000>.

## Cloudflare Pages

Connect the `lex127/webfixbench` repository and use:

- Production branch: `main`
- Build command: leave empty
- Build output directory: `site`

Recommended custom domain: `webfixbench.alexsinyaev.com`.

No environment variables are required for the landing page.
