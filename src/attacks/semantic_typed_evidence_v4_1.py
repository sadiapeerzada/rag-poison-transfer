"""Fail-closed, train-only 2Wiki typed-source diagnostic binding.

Checks corpus identities and *literal* film/director/person relationships. It
never proves global factual truth, authenticates AI reviewers, or permits
construction/injection. Earlier chronology and held-out code remain untouched.
"""
import hashlib
import re

SCHEMA = "rag-poison-transfer.twowiki-v4.1-typed-source-binding/v1"
SCOPE = "development"


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _name_parts(text):
    return re.findall(r"[^\W\d_]+", text.casefold(), re.UNICODE)


def _name_match(credit, lead):
    a, b = _name_parts(credit), _name_parts(lead)
    if len(a) < 2 or len(b) < 2 or a[0] != b[0] or a[-1] != b[-1]:
        return None
    if a == b:
        return "exact"
    # Initial expansion or omission is a caveat, not an authenticated alias.
    middle_a, middle_b = a[1:-1], b[1:-1]
    if middle_a and middle_b and not (len(middle_a) == len(middle_b) and
        all(x[0] == y[0] for x, y in zip(middle_a, middle_b))):
        return None
    if middle_a and middle_b and len(middle_a) != len(middle_b):
        return None
    return "name_variant_requires_review"


def _shape(question):
    patterns = (
        ("country", r"Do both films: (.+?) and (.+?) have the directors from the same country\?"),
        ("nationality", r"Do both directors of films (.+?) and (.+?) share the same nationality\?"),
        ("death", r"Where was the place of death of the director of film (.+)\?"),
        ("birth", r"Where was the director of film (.+) born\?"),
    )
    for kind, pattern in patterns:
        m = re.fullmatch(pattern, question, re.I)
        if m and (kind not in ("country", "nationality") or question.count(" and ") == 1):
            return kind, list(m.groups())
    raise ValueError("Unsupported or ambiguous v4.1 question grammar")


def _film_name(title):
    # Wikipedia disambiguators are never silently equated with title text.
    return re.sub(r"\s+\(\d{4}\s+film\)$", "", title, flags=re.I)


def _film_director(text):
    fragment = re.search(r"\bdirected by\s+(.+)", text, re.I)
    if fragment is None:
        raise ValueError("Director credit missing")
    # A director name is at least two capitalized tokens; retain middle initials
    # while stopping before a following sentence (e.g. "Saša Gedeon. It was...").
    name = re.match(
        r"\s*([A-ZÀ-ÖØ-Þ][^\W\d_]+(?:\s+(?:[A-ZÀ-ÖØ-Þ][^\W\d_]+|[A-Z]\.)){1,4})",
        fragment.group(1), re.UNICODE,
    )
    if name is None:
        raise ValueError("Director credit cannot be parsed without guessing")
    return name.group(1)


def _person_name(text):
    m = re.match(r"^([^()]{3,90}?)\s*\(", text)
    if m is None:
        raise ValueError("Person document lacks named lead")
    return m.group(1).strip()


def _nationality_label(text):
    m = re.search(r"\b(?:is|was)\s+an?\s+([A-Z][a-z]+)\s+(?:film|filmmaker|director|actor)\b", text)
    if m is None:
        raise ValueError("Person nationality not directly stated")
    return m.group(1).casefold()


def bind_typed_sources(query, corpus, expected_source_sha256, *, scope="development"):
    """Bind only pinned gold-support documents; return provisional diagnostics.

    expected_source_sha256 is independently pinned by caller to the dataset;
    a hash map constructed from the input corpus itself proves nothing.
    """
    if scope != SCOPE:
        raise ValueError("v4.1 refuses held-out scope")
    if not isinstance(query, dict) or not isinstance(corpus, list) or not corpus:
        raise ValueError("Pinned query and corpus required")
    if not isinstance(expected_source_sha256, dict):
        raise ValueError("Independently pinned source hashes required")
    allowed = query.get("gold_doc_ids")
    if not isinstance(allowed, list) or len(allowed) not in (2, 4) or len(set(allowed)) != len(allowed):
        raise ValueError("Exact, unique gold support document IDs required")
    if set(expected_source_sha256) != set(allowed):
        raise ValueError("Expected source identities mismatch")
    if any(not isinstance(d, dict) or "doc_id" not in d or "text" not in d for d in corpus):
        raise ValueError("Malformed corpus")
    docs = {d["doc_id"]: d["text"] for d in corpus}
    if len(docs) != len(corpus):
        raise ValueError("Duplicate corpus document ID")
    for doc_id in allowed:
        if doc_id not in docs or not isinstance(docs[doc_id], str):
            raise ValueError("Supporting source missing")
        if _sha(docs[doc_id]) != expected_source_sha256[doc_id]:
            raise ValueError("Pinned source document hash mismatch")

    kind, titles = _shape(query.get("question", ""))
    if len(allowed) != (4 if len(titles) == 2 else 2):
        raise ValueError("Incorrect number of two-hop evidence documents")
    if not isinstance(query.get("gold_answer"), str):
        raise ValueError("Missing gold answer")
    aliases = query.get("gold_aliases", [])
    if not isinstance(aliases, list) or any(not isinstance(x, str) for x in aliases):
        raise ValueError("Invalid declared gold aliases")

    selected = {doc_id: docs[doc_id] for doc_id in allowed}
    assignments = []
    used = set()
    caveats = []
    for title in titles:
        clean_title = _film_name(title)
        film_candidates = [(i, t) for i, t in selected.items() if i not in used and
            re.match(re.escape(clean_title) + r"\b", t, re.I) and
            re.search(r"\bfilm\b", t[:200], re.I)]
        if len(film_candidates) != 1:
            raise ValueError("Film title not uniquely bound to source")
        film_id, film_text = film_candidates[0]
        director = _film_director(film_text)
        person_candidates = []
        for person_id, person_text in selected.items():
            if person_id in used or person_id == film_id:
                continue
            try:
                match_kind = _name_match(director, _person_name(person_text))
            except ValueError:
                continue
            if match_kind is not None:
                person_candidates.append((person_id, person_text, match_kind))
        if len(person_candidates) != 1:
            raise ValueError("Director identity not uniquely bound to person source")
        person_id, person_text, match_kind = person_candidates[0]
        used.update((film_id, person_id))
        if match_kind != "exact":
            caveats.append({"director_credit": director, "person_document": _person_name(person_text),
                            "issue": match_kind})
        if director.casefold() == "henry edwards":
            if "Chrissie White" not in film_text or "Chrissie White" not in person_text:
                raise ValueError("Henry Edwards referent lacks co-star disambiguation")
        assignments.append((title, film_id, person_id, person_text))
    if used != set(allowed):
        raise ValueError("Unmatched extra gold source documents")

    gold = query["gold_answer"].strip()
    if kind in ("country", "nationality"):
        if gold.casefold() not in ("yes", "no"):
            raise ValueError("Gold answer not Boolean")
        labels = [_nationality_label(row[3]) for row in assignments]
        if (labels[0] == labels[1]) != (gold.casefold() == "yes"):
            raise ValueError("Gold does not match supplied nationality labels")
        if kind == "country":
            caveats.append({"issue": "same_country_inferred_from_nationality_label_only"})
        fact = {"nationality_labels": labels}
    else:
        person_text = assignments[0][3]
        pattern = (r"\bdied\s+in\s+" if kind == "death" else
                   r"\bborn\b[^()]{0,70}?\bin\s+") + re.escape(gold) + r"(?=\W|$)"
        if re.search(pattern, person_text, re.I) is None:
            raise ValueError("Gold location not explicitly supported by person source")
        fact = {"explicit_gold_place": gold, "relation": kind}

    return {
        "schema": SCHEMA, "scope": SCOPE, "query_id": query["query_id"],
        "status": "source_text_compatible_unverified", "relation_type": kind,
        "source_sha256": {i: expected_source_sha256[i] for i in sorted(allowed)},
        "source_chains": [{"film": t, "film_doc_id": f, "director_doc_id": p}
                          for t, f, p, _ in assignments],
        "observations": fact, "caveats": caveats,
        "ai_review_provenance_authenticated": False,
        "construction_eligible": False, "factual_approval": False,
        "injection_approved": False, "heldout_authorized": False,
    }
