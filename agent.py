"""
The FitFindr planning loop.

This is the file that makes FitFindr an agent rather than a script. It decides
which tool to run next based on what the last one returned.

If your loop calls all three tools no matter what comes back, you have a list
of function calls. A loop looks at the last result before it picks the next
step. **That branch is the graded part of this unit.**

Build and test your three tools in `tools.py` first. Then come here.

    python agent.py          runs both example paths below
"""

import re

import config
import trace
from tools import search_listings, suggest_outfit, create_fit_card
from generate import ModelUnavailable


# ── session state ─────────────────────────────────────────────────────────────

def new_session(query: str, wardrobe: dict) -> dict:
    """
    A fresh session for one user interaction.

    The session is the single source of truth for a run. Every tool result goes
    in here, and the next tool reads it back out.

    You could pass values straight from one call to the next. It would work,
    and you would not be able to test it — you can't print a variable you have
    already overwritten. Going through the session is what makes the state
    visible, and unit 4 has you write a criterion about exactly that.

    Add fields if you need them.
    """
    return {
        "query": query,              # what the user typed
        "parsed": {},                # description / size / max_price you pulled out of it
        "search_results": [],        # everything search_listings returned
        "selected_item": None,       # the one you chose — goes into suggest_outfit
        "wardrobe": wardrobe,        # the user's wardrobe
        "outfit_suggestion": None,   # what suggest_outfit returned
        "outfit_item_id": None,      # id of the item that actually reached suggest_outfit
        "fit_card": None,            # what create_fit_card returned
        "error": None,               # set when the run ended early
    }


# ── query parsing ─────────────────────────────────────────────────────────────

# Parsing is done with regexes rather than a model call. It costs nothing, it
# gives the same answer every time, and a wrong parse is something I can see in
# session["parsed"] instead of having to re-run the model to reproduce it.

# "under $30", "below 30", "less than $30", "max $30", and a bare "$30".
_PRICE_RE = re.compile(
    r"(?:under|below|less\s+than|max(?:imum)?|up\s+to|cheaper\s+than|"
    r"no\s+more\s+than)\s*\$?\s*(\d+(?:\.\d+)?)",
    re.I,
)
_BARE_PRICE_RE = re.compile(r"\$\s*(\d+(?:\.\d+)?)")

# The sizes the data actually uses: letters, shoe sizes, waist sizes, one size.
# Longest alternatives first — otherwise "xxs" matches as "xs".
_SIZE_WORD = (
    r"(?:xxs|xxl|xs|xl|s|m|l"
    r"|one\s*size"
    r"|(?:us|eu|uk)\s*\d+(?:\.\d+)?"
    r"|w\d{2}(?:\s*l\d{2})?"
    r"|\d+(?:\.\d+)?)"
)
_SIZE_RE = re.compile(rf"\bsizes?[:\s]+({_SIZE_WORD})\b", re.I)

# Sizes that need no "size" in front of them to be unambiguous.
_BARE_SIZE_RE = re.compile(
    r"\b((?:us|eu|uk)\s*\d+(?:\.\d+)?|w\d{2}(?:\s*l\d{2})?|one\s*size)\b",
    re.I,
)

# How people open a request. None of it describes the item.
_LEAD_IN_RE = re.compile(
    r"^(?:i\s*'?m\s+)?(?:looking\s+for|searching\s+for|find\s+me|show\s+me|"
    r"get\s+me|i\s+want|i\s+need|do\s+you\s+have|any)\s+",
    re.I,
)

# Words that mean nothing on their own once a filter has been cut out of the
# middle of the query.
_EDGE_FILLER = {
    "a", "an", "the", "in", "for", "of", "and", "size", "sizes", "under",
    "just", "some", "any", "me",
}


def _description_from(text: str, spans: list[tuple[int, int]]) -> str:
    """What's left of the query once the size and price phrases are cut out."""
    for start, end in sorted(spans, reverse=True):
        text = text[:start] + " " + text[end:]

    text = _LEAD_IN_RE.sub("", text.strip())
    words = re.sub(r"\s+", " ", text).split()
    while words and words[0].lower().strip(",.") in _EDGE_FILLER:
        words.pop(0)
    while words and words[-1].lower().strip(",.") in _EDGE_FILLER:
        words.pop()
    return " ".join(words).strip(" ,.-:")


def parse_query(query: str) -> dict:
    """
    Pull a description, a size and a price ceiling out of what the user typed.

    Args:
        query: the raw query, e.g. "vintage graphic tee under $30, size M".

    Returns:
        A dict with keys 'description' (str), 'size' (str or None) and
        'max_price' (float or None) — the three arguments search_listings takes.
        Sizes come back normalised and upper-cased ("us 9" → "US 9").

        'description' is never empty: if cutting the filters out leaves nothing,
        it falls back to the raw query. Searching with nothing when the user
        typed something would report "no matches" for a parsing bug.
    """
    text = query or ""
    spans: list[tuple[int, int]] = []

    max_price = None
    match = _PRICE_RE.search(text) or _BARE_PRICE_RE.search(text)
    if match:
        max_price = float(match.group(1))
        spans.append(match.span())

    size = None
    match = _SIZE_RE.search(text) or _BARE_SIZE_RE.search(text)
    if match:
        size = " ".join(match.group(1).split()).upper()
        spans.append(match.span())

    return {
        "description": _description_from(text, spans) or text.strip(),
        "size": size,
        "max_price": max_price,
    }


def _nothing_matched(parsed: dict) -> str:
    """
    The message the empty-search branch puts in session["error"].

    "No results" tells the user nothing. This names what was searched for and
    which part of it to loosen, because every filter it mentions is one the
    user can change.
    """
    tried = [f'"{parsed["description"]}"']
    if parsed["size"]:
        tried.append(f"size {parsed['size']}")
    if parsed["max_price"] is not None:
        tried.append(f"under ${parsed['max_price']:.0f}")

    fixes = []
    if parsed["max_price"] is not None:
        fixes.append(f"raising the ceiling above ${parsed['max_price']:.0f}")
    if parsed["size"]:
        fixes.append(f"dropping the size filter or trying one next to {parsed['size']}")
    fixes.append("describing the item in plainer words")
    if len(fixes) > 1:
        fixes = [", ".join(fixes[:-1]) + ", or " + fixes[-1]]

    return (
        f"Nothing in the listings matches {', '.join(tried)}. Try {fixes[0]}."
    )


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Run the loop once and return the finished session.

    Args:
        query:    what the user asked for, in plain language
                  (e.g. "vintage graphic tee under $30, size M").
        wardrobe: a wardrobe dict — get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py.

    Returns:
        The session dict. **Check session["error"] first** — if it isn't None,
        the run ended early and the later fields will still be None.

    ─────────────────────────────────────────────────────────────────────────
    How it decides what to do next.

    The loop holds one variable, `step`, and each pass sets it from what the
    last tool returned. That is the whole difference between this and a list of
    three function calls: nothing below runs because it is next in the file, it
    runs because the step before it said so.

    **The branch** (Milestone 2): if search_listings comes back with an empty
    list, the run puts a message in session["error"] and stops. suggest_outfit
    is never called with nothing. Otherwise it takes the first result — the
    highest-scoring one — and carries on to suggest_outfit.

    Every pass calls trace.check_iterations(), which raises if the count passes
    MAX_ITERATIONS in config.py. The matching path takes five passes and the
    empty one takes two, so this loop will not hit it; the call is there because
    a loop with no stop condition is the standard way an agent burns a quota.

    Parsing is regex-based — see parse_query() above for why.

    ─────────────────────────────────────────────────────────────────────────
    IN UNIT 4 you come back and add two things:

      • Trace calls. One per step. `trace.step("search_listings", inputs=...,
        returned=...)` — see trace.py. Your README needs the output.

      • A handler for ModelUnavailable, so a bad key produces a message rather
        than a stack trace. The import is already at the top of this file.
    """
    session = new_session(query, wardrobe)
    step = "parse"
    iterations = 0

    while step != "stop":
        iterations += 1
        trace.check_iterations(iterations)

        if step == "parse":
            session["parsed"] = parse_query(session["query"])
            step = "search"

        elif step == "search":
            parsed = session["parsed"]
            session["search_results"] = search_listings(
                parsed["description"], parsed["size"], parsed["max_price"]
            )

            # ── THE BRANCH ───────────────────────────────────────────────────
            # Nothing came back, so there is nothing to style. Say what the
            # user could change and stop here.
            if not session["search_results"]:
                session["error"] = _nothing_matched(parsed)
                step = "stop"
            else:
                step = "select"

        elif step == "select":
            # The results are sorted best-first, so the first one is the pick.
            # It goes in the session rather than a local, so the next step
            # reads the same value anyone debugging the run can see.
            session["selected_item"] = session["search_results"][0]
            step = "suggest"

        elif step == "suggest":
            # The pick is read back out of the session, not carried in a local
            # from the step before. The id goes in too, so there are two
            # records to compare: what was selected, and what the tool got.
            item = session["selected_item"]
            session["outfit_item_id"] = item["id"]
            session["outfit_suggestion"] = suggest_outfit(item, session["wardrobe"])
            step = "card"

        elif step == "card":
            session["fit_card"] = create_fit_card(
                session["outfit_suggestion"], session["selected_item"]
            )
            step = "stop"

        else:
            # A step name nothing sets. Without this the loop would spin until
            # check_iterations stopped it, and the traceback would blame the
            # iteration count rather than the typo that caused it.
            raise RuntimeError(f"run_agent reached an unknown step: {step!r}")

    return session


# ── running it directly ──────────────────────────────────────────────

def _brief(value) -> str:
    """One readable line for a session field. The whole listings list is not one."""
    if isinstance(value, dict) and "id" in value and "title" in value:
        return f"{value['id']} — {value['title']} (${value['price']})"
    if isinstance(value, list):
        if not value:
            return "[] (empty)"
        ids = ", ".join(str(entry.get("id", entry)) for entry in value[:4])
        more = f" +{len(value) - 4} more" if len(value) > 4 else ""
        return f"{len(value)} items: {ids}{more}"
    text = " ".join(str(value).split())
    return text if len(text) <= 100 else text[:100] + "…"


def _print_session(session: dict) -> None:
    """Every field of the finished session, one per line — the state the run left."""
    print("  session:")
    for key, value in session.items():
        print(f"    {key:18} = {_brief(value)}")


def _check_selection(session: dict) -> None:
    """
    The same item, written down twice, by two different steps.

    `selected_item` is what the select step picked; `outfit_item_id` is the id
    the suggest step was actually called with. The two can only disagree if
    something travelled between steps outside the session, which is the whole
    reason state goes through it.
    """
    picked = (session["selected_item"] or {}).get("id")
    reached = session["outfit_item_id"]
    verdict = "same item" if picked is not None and picked == reached else "MISMATCH"
    print(f"  selected_item={picked}  reached suggest_outfit={reached}  → {verdict}")


if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe

    print("=== A query the data can match ===")
    matched = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    item = matched["selected_item"] or {}
    print(f"  found:    {item.get('title')} — ${item.get('price')} on {item.get('platform')}")
    print(f"  outfit:   {matched['outfit_suggestion']}")
    print(f"  fit card: {matched['fit_card']}")
    print()
    _check_selection(matched)
    _print_session(matched)

    print()
    print("=== A query it can't ===")
    empty = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"  stopped:  {empty['error']}")
    print(f"  fit_card is {empty['fit_card']!r} — it should still be None here")
    print()
    _print_session(empty)

    print()
    print("The second one should stop before the fit card.")
    print("If both paths look the same, the branch isn't doing anything yet.")
