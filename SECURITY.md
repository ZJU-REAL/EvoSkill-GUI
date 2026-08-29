# Security Policy

Do not commit API keys, access tokens, private endpoints, `.env` files, model
credentials, or raw trajectories containing user data. Use `.env.example` only
for documented placeholder values.

If a credential is committed, revoke it before removing it from Git history.
Deleting it in a later commit is not sufficient. Report security issues through
GitHub's private vulnerability-reporting feature when it is available for the
repository.

The files `docker/adbkey` and
`docker/mastodon-docker/reverse-proxy/certs/10.0.2.2.key` are public,
non-production fixtures inherited from MobileWorld. They are used only inside
the reproducible emulator environment and must never be replaced with personal
or production keys.
