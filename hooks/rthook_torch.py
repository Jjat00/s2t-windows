# Runtime hook: pre-import torch so its internal modules initialize
# in the correct order before our app code runs.
# Fixes "circular import" errors in PyInstaller onedir builds.
import torch  # noqa: F401
