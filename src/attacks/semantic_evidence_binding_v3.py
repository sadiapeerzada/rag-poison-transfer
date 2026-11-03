"""Development-only, source-grounded chronology evidence binding.

This establishes document identity and limited syntactic relationships.
It does not establish factual truth or independently resolve pronouns.
"""
import hashlib
import re


def _name_compatible(left, right):
    a = re.findall(r"[A-Za-z]+", left.casefold())
    b = re.findall(r"[A-Za-z]+", right.casefold())
    if len(a) < 2 or len(b) < 2:
        return False
    if a[0] != b[0] or a[-1] != b[-1]:
        return False
    middle_a, middle_b = a[1:-1], b[1:-1]
    if not middle_a or not middle_b:
        return True
    return len(middle_a) == len(middle_b) and all(
        x[0] == y[0] for x, y in zip(middle_a, middle_b)
    )


def bind_chronology(query, corpus, evidence):
    """Check an explicit two-document evidence chain, fail closed."""
    if evidence["query_id"] != query["query_id"]:
        raise ValueError("query identity mismatch")

    allowed = set(query.get("gold_doc_ids", []))
    docs = {row["doc_id"]: row["text"] for row in corpus}
    if len(docs) != len(corpus):
        raise ValueError("duplicate corpus document ID")

    for role in ("source", "relation"):
        doc_id = evidence[f"{role}_doc_id"]
        quote = evidence[f"{role}_quote"]
        if doc_id not in allowed or doc_id not in docs:
            raise ValueError("document not in query supporting sources")
        if not isinstance(quote, str) or len(quote) < 25:
            raise ValueError("invalid evidence quotation")
        if quote not in docs[doc_id]:
            raise ValueError("quotation not found verbatim in source")

    name = evidence["source_name"]
    relation_name = evidence["relation_name"]
    source_quote = evidence["source_quote"]
    relation_quote = evidence["relation_quote"]

    if not _name_compatible(name, relation_name):
        raise ValueError("source and relation names incompatible")
    if not source_quote.startswith(name):
        raise ValueError("source quotation does not identify referent")

    birth = re.match(
        re.escape(name)
        + r"\s*\((?:born\s+)?[A-Za-z]+\s+\d{1,2},\s+(\d{4})",
        source_quote,
        re.I,
    )
    if birth is None:
        raise ValueError("explicit birth-year evidence unavailable")

    year = int(birth.group(1))
    question = query["question"]

    film = re.fullmatch(
        r"When was the director of film (.+) born\?", question, re.I
    )
    father = re.fullmatch(
        r"When did (.+)'s father die\?", question, re.I
    )

    if film:
        if not relation_quote.casefold().startswith(film.group(1).casefold()):
            raise ValueError("film identity mismatch")
        if not re.search(
            r"\bdirected\s+by\s+" + re.escape(relation_name)
            + r"(?=[\s.,;]|$)",
            relation_quote,
            re.I,
        ):
            raise ValueError("director relationship not explicit")
        status = "direct_relation_text_grounded"
        usable_year = year

    elif father:
        relation_document = docs[evidence["relation_doc_id"]]
        header = re.match(
            r"([A-Za-z]+(?:\s+[A-Za-z.]+){1,4})\s*\(",
            relation_document,
        )
        if not header or not _name_compatible(
            father.group(1), header.group(1)
        ):
            raise ValueError("child identity mismatch")

        if not re.search(
            r"\bto\s+(?:historian\s+)?"
            + re.escape(relation_name)
            + r"(?=[\s.,;]|$)",
            relation_quote,
            re.I,
        ):
            raise ValueError("parent relationship not explicit")

        # 'He was born to ...' still requires coreference resolution.
        status = "coreference_requires_independent_review"
        usable_year = None

    else:
        raise ValueError("unsupported chronology relationship")

    return {
        "status": status,
        "documented_birth_year": usable_year,
        "suggested_birth_year": year,
        "factual_approval": False,
        "source_document_sha256": hashlib.sha256(
            docs[evidence["source_doc_id"]].encode()
        ).hexdigest(),
        "relation_document_sha256": hashlib.sha256(
            docs[evidence["relation_doc_id"]].encode()
        ).hexdigest(),
    }
