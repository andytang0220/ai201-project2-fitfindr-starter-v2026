"""
The runs your test needs. ← UNIT 4, MILESTONE 3

Each of your five criteria needs something run against it. A criterion about
the empty-search branch needs an impossible query. One about the fit card needs
the same item run more than once. Working that out is Milestone 3's first step,
and this file is where you write it down.

`run_eval.py` runs everything here five times and writes the run log — five
because your criteria are written out of five.

Three scenarios are filled in to show the shape. Add or change whatever your
own criteria need — these are a starting point, not a fixed set.
"""

SCENARIOS = [
    {
        # A query the data can match. Criterion 1.
        "name": "matching query completes",
        "query": "vintage graphic tee under $30",
        "wardrobe": "example",
        "criterion": 1,
    },
    {
        # A query nothing can match. Criterion 2 — the branch.
        "name": "impossible query stops early",
        "query": "designer ballgown size XXS under $5",
        "wardrobe": "example",
        "criterion": 2,
    },
    {
        # A user with nothing saved. One of unit 4's three failure modes.
        "name": "empty wardrobe",
        "query": "denim jacket under $50",
        "wardrobe": "empty",
        "criterion": None,
    },
    # ── Criterion 3: state ───────────────────────────────────────────────────
    # "Across 5 matching queries, the id in session['selected_item'] is the
    # same id that appears in the suggest_outfit trace line's inputs — 5/5."
    #
    # What matters is what lands in the session, not the wording, so these are
    # ordinary matching queries chosen to exercise different parse shapes
    # (a size filter, a bare shoe size, no filters at all). Each one is run
    # five times by run_eval.py; compare selected_item["id"] against the
    # inputs on the suggest_outfit trace line for every try.
    {
        "name": "state: selected item reaches suggest_outfit (size filter)",
        "query": "90s track jacket size M",
        "wardrobe": "example",
        "criterion": 3,
    },
    {
        "name": "state: selected item reaches suggest_outfit (shoe size)",
        "query": "black platform mary janes US 7",
        "wardrobe": "example",
        "criterion": 3,
    },
    {
        "name": "state: selected item reaches suggest_outfit (no filters)",
        "query": "chunky knit cardigan one size",
        "wardrobe": "example",
        "criterion": 3,
    },
    # ── Criterion 4: fit card with no outfit ─────────────────────────────────
    # "Given an empty or whitespace-only outfit, the agent does not mention
    # anything about how the item fits into an outfit — 5 of 5."
    #
    # suggest_outfit() never returns an empty string on purpose (it falls back
    # to a non-empty message), so a plain query can't reach this branch on its
    # own. "outfit_override" is the outfit string the fit-card step is handed
    # instead of suggest_outfit's reply: run_once passes it to run_agent, which
    # skips the suggest_outfit call and says so in the trace. Two forms: empty,
    # and whitespace-only.
    {
        "name": "fit card with empty outfit",
        "query": "cropped denim jacket $45",
        "wardrobe": "example",
        "criterion": 4,
        "outfit_override": "",
    },
    {
        "name": "fit card with whitespace-only outfit",
        "query": "cropped denim jacket $45",
        "wardrobe": "example",
        "criterion": 4,
        "outfit_override": "   \n\t  ",
    },
    # ── Criterion 5: max_price is respected ──────────────────────────────────
    # "The results of a search have a price <= the provided max_price in
    # 5 of 5 tries, given that a max_price is provided."
    #
    # One query per price phrasing parse_query() accepts ("under $N",
    # "max $N", a bare "$N"), plus a boundary case where the best match costs
    # exactly max_price — the filter is inclusive, so it must still appear.
    # Check every entry in session["search_results"], not just the pick.
    {
        "name": "max_price: 'under $25'",
        "query": "oversized flannel shirt under $25",
        "wardrobe": "example",
        "criterion": 5,
    },
    {
        "name": "max_price: 'max $20'",
        "query": "vintage band tee max $20",
        "wardrobe": "example",
        "criterion": 5,
    },
    {
        "name": "max_price: bare '$45'",
        "query": "cropped denim jacket $45",
        "wardrobe": "example",
        "criterion": 5,
    },
    {
        "name": "max_price: boundary, item priced exactly at the ceiling",
        "query": "graphic tee under $24",
        "wardrobe": "example",
        "criterion": 5,
    },
]

WARDROBES = ("example", "empty")


def validate() -> list[str]:
    """Complain about anything malformed, before a long run rather than during."""
    problems = []
    for i, scenario in enumerate(SCENARIOS, 1):
        if not scenario.get("query", "").strip():
            problems.append(f"scenario {i} has no query")
        if scenario.get("wardrobe") not in WARDROBES:
            problems.append(
                f"scenario {i} has wardrobe {scenario.get('wardrobe')!r} — "
                f"it should be one of {WARDROBES}"
            )
    return problems
