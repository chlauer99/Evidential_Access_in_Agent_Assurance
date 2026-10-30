"""Resolve read-only judge URLs within the configured FHIR origin and path."""
from urllib.parse import unquote, urljoin, urlsplit


def resolve_fhir_url(reference: str, base: str) -> str:
    """Allow the FHIR root (including ?_getpages) and its child paths only.

    Raises ValueError for a different origin, credentials, fragments, or paths
    outside the FHIR root. Resource-relative and root-relative links are supported.
    """
    if any(ord(c) <= 32 for c in reference) or "\\" in reference:
        raise ValueError("Invalid characters in URL")
    root = urlsplit(base)
    target = urljoin(base.rstrip("/") + "/", reference)
    parsed = urlsplit(target)

    def origin(url):
        return url.scheme.lower(), url.hostname, url.port or {"http": 80, "https": 443}.get(url.scheme)

    if (root.scheme not in {"http", "https"} or origin(parsed) != origin(root)
            or parsed.username is not None or parsed.password is not None or parsed.fragment):
        raise ValueError("URL must use the configured FHIR origin")
    path = unquote(parsed.path)
    prefix = unquote(root.path).rstrip("/")
    if ("\\" in path or any(segment in {".", ".."} for segment in path.split("/"))
            or not (path == prefix or path.startswith(prefix + "/"))):
        raise ValueError("URL must stay within the configured FHIR path")
    return target
