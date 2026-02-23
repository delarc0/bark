import json
import logging
import urllib.request

from config import cfg

log = logging.getLogger(__name__)

GITHUB_RELEASES_URL = "https://api.github.com/repos/delarc0/bark/releases/latest"


def check_for_update():
    """Check GitHub for a newer release. Returns version string or None."""
    try:
        req = urllib.request.Request(
            GITHUB_RELEASES_URL,
            headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Bark",
            },
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        latest = data.get("tag_name", "").lstrip("v")
        current = cfg["version"]
        if latest and latest != current:
            try:
                lv = tuple(int(x) for x in latest.split("."))
                cv = tuple(int(x) for x in current.split("."))
                if lv > cv:
                    return latest
            except (ValueError, TypeError):
                return latest
    except Exception as e:
        log.debug(f"Version check failed: {e}")
    return None
