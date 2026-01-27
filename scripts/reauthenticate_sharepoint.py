"""
Script to re-authenticate with SharePoint/OneDrive by deleting the cached MSAL token
and triggering a new interactive OAuth flow.

Usage:
    uv run scripts/reauthenticate_sharepoint.py
"""

import json
from pathlib import Path

CLIENT_CONFIG_FILE = Path.home() / ".azure_client.json"
TOKEN_CACHE_FILE = Path.home() / ".msal_token_cache.json"
SCOPES = ["Files.ReadWrite"]


def reauthenticate_sharepoint() -> bool:
    """
    Deletes the cached MSAL token and triggers a new interactive authentication flow.
    Returns True if successful, False otherwise.
    """
    if TOKEN_CACHE_FILE.exists():
        try:
            TOKEN_CACHE_FILE.unlink()
            print(f"Deleted cached token: {TOKEN_CACHE_FILE}")
        except Exception as e:
            print(f"Error deleting token: {e}")
            return False
    else:
        print("No cached token found. Starting fresh authentication.")

    if not CLIENT_CONFIG_FILE.exists():
        print(f"Error: Client configuration not found at {CLIENT_CONFIG_FILE}")
        print("Please ensure you have your Azure client configuration JSON file.")
        print('Example: {"client_id": "...", "authority": "..."}')
        return False

    try:
        # Lazy imports to avoid dependency issues for non-workspace users
        import msal

        config = json.loads(CLIENT_CONFIG_FILE.read_text(encoding="utf-8"))
        client_id = config.get("client_id")
        authority = config.get("authority")

        if not client_id or not authority:
            print("Error: Config file must contain both 'client_id' and 'authority'")
            return False

        cache = msal.SerializableTokenCache()
        # Note: We already deleted the file if it existed, so we start with an empty
        # cache

        app = msal.PublicClientApplication(
            client_id=client_id,
            authority=authority,
            token_cache=cache,
        )

        print("Opening browser for interactive authentication...")
        result = app.acquire_token_interactive(SCOPES)

        if "access_token" in result:
            if cache.has_state_changed:
                TOKEN_CACHE_FILE.write_text(cache.serialize(), encoding="utf-8")
                print(
                    f"Successfully re-authenticated. Token cache saved to "
                    f"{TOKEN_CACHE_FILE}"
                )
                return True
            else:
                print("Authentication successful, but cache state did not change.")
                return True
        else:
            error_msg = (
                result.get("error_description")
                or result.get("error")
                or "Unknown error"
            )
            print(f"Error during re-authentication: {error_msg}")
            return False

    except ImportError:
        print(
            "Error: msal not installed. "
            "Run 'uv sync --extra sharepoint' (or equivalent) to install it."
        )
        return False
    except Exception as e:
        print(f"Error during re-authentication: {e}")
        return False


if __name__ == "__main__":
    reauthenticate_sharepoint()
