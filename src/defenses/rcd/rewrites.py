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

    if lowered.startswith("which "):
        rewrites.append("what " + q[7:])
    elif lowered.startswith("what "):
        rewrites.append("which " + q[5:])
    elif lowered.startswith("who "):
        rewrites.append(
            q.replace(
                "Who ",
                "Which person ",
                1,
            )
        )
    elif lowered.startswith("where "):
        rewrites.append(
            q.replace(
                "Where ",
                "In what place ",
                1,
            )
        )
    elif lowered.startswith("when "):
        rewrites.append(
            q.replace(
                "When ",
                "In what year or date ",
                1,
            )
        )
    elif lowered.startswith("how "):
        rewrites.append(
            q.replace(
                "How ",
                "In what way ",
                1,
            )
        )
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
    """Generate N additional query rewrites, excluding the original query."""
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
