# GitHub Publication Checklist

This directory is the screened publication copy. The original local workspace is
not the publication root.

## Intentionally Excluded

- `.env` and machine-specific credentials
- `.venv`, Python caches, and package build output
- `traj_logs*`, generated skill stores, screenshots, and runtime artifacts
- `.capability_reuse_backup` and `.refine_p0_backup`
- the downloaded accessibility-forwarder APK

## Before the First Push

1. Review `git status` and the staged diff.
2. Add the new GitHub repository as `origin`; keep MobileWorld as `upstream`.
3. Replace or add repository URLs in `pyproject.toml` after the public URL exists.
4. Add the final CoEvoSkill paper citation when it is available.
5. Run the secret scan, compile check, and focused tests documented below.

```bash
git status --short
git diff --check
uv run python -m compileall -q src tools/a11y_tree_tool/a11y_tool
uv run ruff check --select E9,F63,F7,F82 src scripts tools/a11y_tree_tool/a11y_tool
uv run pytest -q tests/test_coevoskill_core.py
```

When the GitHub repository exists:

```bash
git remote rename origin upstream  # only if origin still points to MobileWorld
git remote add origin https://github.com/YOUR_ACCOUNT/CoEvoSkill.git
git add -A
git commit -m "release: prepare CoEvoSkill source"
git push -u origin HEAD:main
```
