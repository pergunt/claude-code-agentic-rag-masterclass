"""Print shell exports for curl tests: public Supabase config + test-user access tokens.

Usage (each Bash call is a fresh shell, so run it at the start of every call that needs tokens):
    eval "$(cd backend && venv/bin/python -m app.scripts.dev_tokens)"
Exports SUPABASE_URL, SUPABASE_ANON_KEY (public, shipped in the frontend bundle anyway),
TOKEN_A / USER_A_ID (rag-test-a@example.com) and TOKEN_B / USER_B_ID (rag-test-b@example.com).
Never prints any other setting.
"""

import shlex
import sys

from app.config import get_settings
from app.db import create_anon_client

# Dev-only password from .claude/memory/dev-test-accounts.md
DEV_TEST_PASSWORD = "TestPass123!"


def sign_in(email: str) -> tuple[str, str]:
    """Sign in a test user and return (access_token, user_id)."""
    res = create_anon_client().auth.sign_in_with_password(
        {"email": email, "password": DEV_TEST_PASSWORD}
    )
    return res.session.access_token, res.user.id


def main() -> None:
    settings = get_settings()
    exports = {
        "SUPABASE_URL": settings.supabase_url,
        "SUPABASE_ANON_KEY": settings.supabase_anon_key,
    }
    try:
        for suffix, email in (("A", "rag-test-a@example.com"), ("B", "rag-test-b@example.com")):
            exports[f"TOKEN_{suffix}"], exports[f"USER_{suffix}_ID"] = sign_in(email)
    except Exception as exc:
        print(f"dev_tokens: sign-in failed: {exc}", file=sys.stderr)
        sys.exit(1)
    for name, value in exports.items():
        print(f"export {name}={shlex.quote(value)}")


if __name__ == "__main__":
    main()
