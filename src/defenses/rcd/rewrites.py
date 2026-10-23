from __future__ import annotations

import re


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _generic_rewrites(query: str) -> list[str]:
    q = _clean(query)

    if not q:
        return []

    rewrites = []

    # Generic reformulation
    rewrites.append(
        f"Can you identify {q[0].lower() + q[1:]}"
    )

    lowered = q.lower()

    # Prefix rewrites. Slice by the prefix length so the remainder of the
    # query is preserved verbatim, independent of the original capitalization.
    if lowered.startswith("which "):
        rewrites.append("what " + q[len("which "):])
    elif lowered.startswith("what "):
        rewrites.append("which " + q[len("what "):])
    elif lowered.startswith("who "):
        rewrites.append("Which person " + q[len("who "):])
    elif lowered.startswith("where "):
        rewrites.append("In what place " + q[len("where "):])
    elif lowered.startswith("when "):
        rewrites.append("In what year or date " + q[len("when "):])
    elif lowered.startswith("how "):
        rewrites.append("In what way " + q[len("how "):])
    else:
        rewrites.append(
            f"What is the answer to: {q}"
        )

    if " have in common" in lowered:
        rewrites.append(
            q.replace(
                " have in common",
                " have shared",
            )
        )
    elif " shared " not in lowered:
        rewrites.append(
            q.rstrip("?") + "?"
        )

    return rewrites


def generate_query_rewrites(
    query: str,
    *,
    n_rewrites: int = 3,
) -> list[str]:
    """Generate up to N additional unique query rewrites, excluding the original query."""
    if n_rewrites <= 0:
        return []

    q = _clean(query)

    if not q:
        return []

    output = []

    for candidate in _generic_rewrites(q):
        candidate = _clean(candidate)

        if candidate and candidate != q and candidate not in output:
            output.append(candidate)

        if len(output) >= n_rewrites:
            break

    return output


def generate_rewrite_set(
    query: str,
    *,
    n_rewrites: int = 3,
) -> list[str]:
    return generate_query_rewrites(
        query,
        n_rewrites=n_rewrites,
    )
