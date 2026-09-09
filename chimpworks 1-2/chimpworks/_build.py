"""Build-time configuration.

The copy in the source tree is the DEV posture (inert). A packaged release
overwrites this file — see ``packaging/write_build_config.py`` — with the real
licensing endpoint, the enforcement flag, and the trusted Ed25519 public keys
before PyInstaller runs. Nothing else in the package writes to it.
"""
from __future__ import annotations

# URL of the deployed licensing Worker, e.g.
# "https://chimpwriter-licensing.<acct>.workers.dev". Empty => unconfigured.
LICENCE_URL: str = ""

# Gate Pro features? Only ever True in a release build alongside a real
# LICENCE_URL and populated TRUSTED_KEYS.
ENFORCE: bool = False

# kid -> base64 raw ed25519 public key. From `npm run gen-keys` in the
# chimpwriter-licensing repo. Add-only for cert-* kids.
TRUSTED_KEYS: dict[str, str] = {}
