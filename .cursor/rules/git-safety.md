# Git safety (AGENT)

## Never commit/push unless explicitly asked

- Do **not** run `git commit`, `git push`, or any command that creates commits or updates remotes unless the user **explicitly** requests it (e.g. “commit this”, “push”, “push to origin”).
- If the user asks to “push”, first show what would be pushed (branch + commit(s)) and wait for an explicit “push” confirmation.
- If the user says **“push changes”**, that means you have permission to **commit any uncommitted changes** (as one or more sensible commits) **and then push** those commits, unless the user specifies otherwise.

## No destructive git operations

- Do not use force pushes (`--force`, `--force-with-lease`) unless the user explicitly requests.
- Do not rewrite public history (e.g., `rebase`, `reset --hard`, `commit --amend`) unless the user explicitly requests.

