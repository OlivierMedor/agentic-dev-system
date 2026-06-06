# Repository Settings

These are suggested public GitHub settings for the repository owner to review
manually in the GitHub UI. The CLI does not configure repository metadata,
visibility, topics, branch protection, or licenses.

For the suggested repository description, topics, website field guidance, and
manual metadata setup steps, see `docs/github_metadata.md`.

## Public Repository Settings

For the public repository:

- Confirm CI passes on the release-readiness PR.
- Confirm branch protection and review expectations are set manually.
- Confirm generated artifacts, runtime queue files, `.env` files, and private
  local guidance are untracked.
- Confirm the README and docs explain that the system does not automatically
  merge, deploy, call cloud models, or approve its own work.
- Confirm the human owner has reviewed the final repository visibility decision.

Topics and the repository description are configured manually in the GitHub UI.
Do not use local workflow commands to change repository metadata.

## License Note

The owner should choose a license before inviting outside reuse. Do not choose
or add a `LICENSE` file automatically unless the owner explicitly requested it.
