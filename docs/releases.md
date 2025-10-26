# Release Process

1. Update the version automatically:

   ```bash
   bump2version patch   # or minor / major
   ```

   This edits `tanx_game/__init__.py`, updates docs tracked in `.bumpversion.cfg`,
   commits the change, and creates a tag `vX.Y.Z`.

2. Push commits and tags:

   ```bash
   git push --follow-tags
   ```

   The GitHub `Release` workflow builds and publishes the desktop and web
   artifacts automatically.

3. (Optional) Update `CHANGELOG.md` or release notes in the GitHub UI with key
   highlights for the new version.
