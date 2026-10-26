# UploadDesk project rules

- Use semantic versions MAJOR.MINOR.PATCH.
- Initial stable version is 1.0.0, only after the user's explicit final approval.
- Breaking API/behavior compatibility changes require a major bump; compatible new features require a minor bump; compatible bug/security fixes require a patch bump.
- Describe compatibility and changes in CHANGELOG.md for each release.
- Until approval, keep VERSION.json version null for the initial release. Later changes remain unreleased until approved.
- Do not commit credentials, .venv, generated images, real HWPX files, browser sessions, or the external News database.
- Publishing to GitHub requires the user's explicit final release approval. Never force-push.
- Every approved version must also be packaged as UploadDesk-vX.Y.Z.zip in C:\Users\21017\Desktop\☆ ChatGPT. Package approved source and setup files, excluding credentials, original documents, generated images, external databases, and nonportable virtual environments. Verify ZIP integrity and the bundled version before reporting success.
- Never automatically click the final KOITA post-save button unless separately authorized.
