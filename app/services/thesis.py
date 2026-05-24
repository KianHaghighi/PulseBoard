import re
from ..models.models import VCFirm, Article

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can", "i", "we", "our",
    "us", "my", "that", "this", "it", "its", "their", "they", "them",
    "which", "who", "what", "how", "when", "where", "why", "not", "no",
    "up", "out", "about", "into", "over", "also", "as", "so", "if",
    "than", "then", "there", "here", "just", "very", "some", "any",
    "all", "both", "each", "other", "such", "only", "while", "new",
    "using", "use", "used", "help", "build", "building", "built",
    "platform", "solution", "product", "company", "startup", "businesses",
    "business", "market", "markets", "space", "across", "within", "one",
    "two", "make", "making", "get", "give", "want", "need", "work",
}


def _tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z]+", (text or "").lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 2]


def _score(keywords: list[str], *text_fields) -> int:
    combined = " ".join(f or "" for f in text_fields).lower()
    return sum(1 for kw in keywords if kw in combined)


def _vc_reason(keywords: list[str], firm: VCFirm) -> str:
    profile = f"{firm.focus_sectors or ''} {firm.description or ''}"
    matched = [kw for kw in keywords if kw in profile.lower()]
    if matched:
        return f"Matches on: {', '.join(matched[:4])}."
    return "Active investor in your target market."


def _article_reason(keywords: list[str], article: Article) -> str:
    text = f"{article.title or ''} {article.content_snippet or ''}"
    matched = [kw for kw in keywords if kw in text.lower()]
    if matched:
        return f"Covers: {', '.join(matched[:4])}."
    if article.category:
        return f"Relevant {article.category} coverage."
    return "Related market intelligence."


def _feedback(keywords: list[str], n_vcs: int, n_articles: int) -> str:
    prominent = sorted({kw for kw in keywords if len(kw) > 4}, key=len, reverse=True)[:5]
    topics = ", ".join(prominent) if prominent else "your target sector"
    vc_str = f"{n_vcs} investor{'s' if n_vcs != 1 else ''}"
    art_str = f"{n_articles} article{'s' if n_articles != 1 else ''}"
    return (
        f"Your thesis centres on {topics}. "
        f"We found {vc_str} whose focus areas align with your space "
        f"and {art_str} covering relevant market developments."
    )


def analyze_thesis(thesis: str) -> dict:
    keywords = _tokenize(thesis)

    firms = VCFirm.query.order_by(VCFirm.name).all()
    articles = (
        Article.query
        .filter(Article.title.isnot(None))
        .order_by(Article.published_at.desc())
        .limit(100)
        .all()
    )

    # Score and rank VCs; fall back to alphabetical order if nothing scores
    scored_firms = sorted(
        firms,
        key=lambda f: -_score(
            keywords, f.focus_sectors, f.description, f.notable_portfolio
        ),
    )
    top_firms = scored_firms[:5]

    # Score and rank articles; only surface ones with at least one keyword hit
    scored_articles = [
        (a, _score(keywords, a.title, a.content_snippet, a.category))
        for a in articles
    ]
    scored_articles = sorted(
        [(a, s) for a, s in scored_articles if s > 0],
        key=lambda x: -x[1],
    )
    top_articles = [a for a, _ in scored_articles[:5]]

    vc_matches = [
        {"id": f.id, "name": f.name, "reason": _vc_reason(keywords, f)}
        for f in top_firms
    ]
    article_matches = [
        {"id": a.id, "reason": _article_reason(keywords, a)}
        for a in top_articles
    ]

    return {
        "thesis_feedback": _feedback(keywords, len(vc_matches), len(article_matches)),
        "vc_matches": vc_matches,
        "article_matches": article_matches,
    }
