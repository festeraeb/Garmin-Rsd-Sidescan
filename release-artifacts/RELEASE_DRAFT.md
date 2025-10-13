# Release draft: v1.0.0-rc.1

This is a local release draft for `v1.0.0-rc.1`.

Published tag: `v1.0.0-rc.1` (pushed to origin)

Included artifacts (zip):

- `release-artifacts/v1.0.0-rc.1.zip` — benchmark outputs, `RELEASE_NOTES/`, and `CHANGELOG.md` (if present)

Release notes (from RELEASE_NOTES/v1.0.0-rc.1.md):

---

See file RELEASE_NOTES/v1.0.0-rc.1.md for the full release notes.

---

How to publish manually (PowerShell):

1) Export your GitHub token into an environment variable:

   $env:GITHUB_TOKEN = 'ghp_xxxYOURTOKENxxx'

2) Create the release via the GitHub API (example PowerShell):

   $body = Get-Content -Raw RELEASE_NOTES\v1.0.0-rc.1.md
   $payload = @{ tag_name = 'v1.0.0-rc.1'; name = 'v1.0.0-rc.1'; body = $body; draft = $false; prerelease = $true } | ConvertTo-Json
   Invoke-RestMethod -Method Post -Headers @{ Authorization = "token $env:GITHUB_TOKEN" } -Uri 'https://api.github.com/repos/festeraeb/Garmin-Rsd-Sidescan/releases' -Body $payload -ContentType 'application/json'

3) Upload the artifact to the release using the returned upload_url (replace RELEASE_ID with the returned ID):

   $upload_url = "https://uploads.github.com/repos/festeraeb/Garmin-Rsd-Sidescan/releases/RELEASE_ID/assets?name=v1.0.0-rc.1.zip"
   Invoke-RestMethod -Method Post -Headers @{ Authorization = "token $env:GITHUB_TOKEN" } -Uri $upload_url -InFile 'release-artifacts/v1.0.0-rc.1.zip' -ContentType 'application/zip'

If you want me to publish the release from this environment, set $env:GITHUB_TOKEN here and I will call the API and upload the artifact.
