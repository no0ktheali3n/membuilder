"""
Metadata enrichment — derives breadcrumb and section context from a page URL.

Example:
    https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/
    → ["Concepts", "Workloads", "Pods", "Pod Lifecycle"]
"""

from urllib.parse import urlparse


def url_to_breadcrumb(url: str, strip_prefix: str = "") -> list[str]:
    """
    Convert a URL path into a human-readable breadcrumb list.

    Args:
        url: Full page URL
        strip_prefix: Path prefix to remove before building crumbs
                      e.g. "/docs" strips the docs root segment

    Returns:
        List of capitalised path segments e.g. ["Concepts", "Workloads", "Pods"]
    """
    path = urlparse(url).path.rstrip("/")

    if strip_prefix:
        prefix = strip_prefix.rstrip("/")
        if path.startswith(prefix):
            path = path[len(prefix):]

    segments = [s for s in path.split("/") if s]

    return [_humanise(s) for s in segments]


def _humanise(segment: str) -> str:
    """
    Turn a URL slug into a readable label.

    Examples:
        pod-lifecycle       → Pod Lifecycle
        kube-apiserver      → Kube Apiserver
        v1beta1             → V1beta1
    """
    return " ".join(word.capitalize() for word in segment.replace("_", "-").split("-"))


def derive_section(url: str, strip_prefix: str = "") -> str:
    """Return the top-level section of a URL (first path segment after prefix)."""
    crumbs = url_to_breadcrumb(url, strip_prefix)
    return crumbs[0] if crumbs else ""