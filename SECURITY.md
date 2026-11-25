# Security policy

Please report suspected vulnerabilities privately to the repository owner rather
than including credentials, tokens, or personal information in public issues.

## Dependency maintenance

Dependabot is configured to check the pinned Python dependencies in
`requirements.txt` and GitHub Actions versions weekly. Review update pull requests
before merging. Enable Dependency graph, Dependabot alerts, and Dependabot security
updates in the repository's security settings.

## Credentials

No custom token is required for the dashboard. The workflow uses GitHub's temporary
`GITHUB_TOKEN` with job-specific permissions. Store any future credentials only in
Settings → Secrets and variables → Actions → New repository secret. Reference a secret
through the Actions secrets context; never put its value into HTML, JavaScript, JSON,
Git history, workflow logs, or public artifacts. Use least privilege and rotate
exposed credentials immediately. Local credential files are excluded by .gitignore,
which does not remove previously tracked secrets or replace secret scanning.

## Repository settings (owner action required)

- Enable Secret scanning and user alerts where available; enable Push protection.
- Enable Dependabot alerts and security updates.
- Protect `main` against deletion and force pushes. Keep ordinary authorized direct
  pushes enabled: the existing data refresh jobs commit validated snapshots directly
  to `main`. Do not require pull requests, required status checks on every push,
  or signed commits until the updater has been redesigned for those requirements.
- Keep write access limited to trusted maintainers and review changes to workflows.

These settings must be enabled in GitHub's repository settings; this document
does not itself enable them.
