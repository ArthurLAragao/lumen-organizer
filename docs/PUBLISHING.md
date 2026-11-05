# Public release and GitHub Pages

The `master` branch contains the portable application source and a public project
showcase in `site/`. GitHub Pages serves that showcase, not the Python runtime.
The Pages workflow verifies the React build and fictional Python regression suite
on Windows, checks the site's local asset links, then deploys only `site/`.

## Verified for this publication

- Lumen frontend TypeScript/production build passed.
- Python suite: **187 tests**, zero failures, errors or skips.
- Public configuration rejects missing/invalid Notion destinations before any provider call.
- Website: navigation, FAQ, copy-button feedback and 375/768/1440px layouts checked.
- No broken local resources or browser JavaScript exceptions in the website smoke check.
- Screenshot captured from the real interface using an isolated empty runtime;
  no personal notes, accounts or transfer histories were used.
- Publication candidates scanned for common credential patterns and the removed
  personal Notion IDs; no matches. This is a focused check, not a security audit.

Personal state (`.local/`), environments, outputs and vault content are ignored.
Portable destinations are documented in `.env.example`; no `.env` auto-loader is
included. The connected Codex/Notion flow still needs the installing user's account
and schema. A successful local suite is not proof of another user's account setup.

Historical implementation evidence is preserved in the other documentation; old
stage labels describe those checkpoints, not the current publication state.

## Updating

Push reviewed changes to `master`. The GitHub Actions workflow publishes only after
its checks pass. View the deployment in Actions and the `github-pages` environment.
Never add credentials to the site, a workflow file, a commit, or a browser bundle.
