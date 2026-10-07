"""
The three FitFindr tools.

Each one is a standalone function you can call and test on its own, before any
of them are wired into the loop. Build and test them one at a time — three
untested tools joined by a loop is one problem that looks like six, because you
can't tell which layer is lying to you.

    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)             → str
    create_fit_card(outfit, new_item)              → str

All three are stubs right now. They run and they do nothing — that's the
starting position and it's deliberate.

⚠️ Before you write any of them, fill in the **Tool Inventory** section of your
README (Milestone 2). Four lines per tool: what it does, each input with its
type, exactly what it returns, and what it returns when it has nothing to give.
That last line is what your loop branches on. "Returns a list" earns nothing —
the description has to say what is *in* the list.
"""

import re

import config
from generate import generate
from utils.data_loader import load_listings


# ── Tool 1: search_listings ───────────────────────────────────────────────────

# Tokens that appear in a size string without naming a size. Without this,
# "US 8" and "US 8.5" would both match on "us" and every shoe would match
# every other shoe.
_SIZE_NOISE = {"us", "eu", "uk", "size"}

# Query words that say nothing about the item.
_STOPWORDS = {
    "a", "an", "and", "are", "for", "i", "in", "is", "it", "looking", "me",
    "my", "need", "of", "on", "or", "size", "some", "something", "that",
    "the", "this", "to", "under", "want", "with",
}

# Words, keeping decimals whole so "8.5" survives and "wash." loses its period.
_WORD_RE = re.compile(r"[a-z0-9]+(?:\.[a-z0-9]+)*")


def _words(text: str) -> set[str]:
    """The lowercase word set for a chunk of text."""
    return set(_WORD_RE.findall((text or "").lower()))


def _size_tokens(size: str) -> set[str]:
    """
    The set of things a size string can be matched on.

    Parentheticals are notes rather than sizes, so they come off: "XL
    (oversized)" is an XL. What's left is kept whole *and* split on "/" and
    spaces, so "S/M" answers to "S" and to "M", and "W30 L30" answers to "W30".
    """
    base = " ".join(re.sub(r"\(.*?\)", " ", (size or "").lower()).split())
    tokens = {base} | {
        part for part in base.replace("/", " ").split()
        if part not in _SIZE_NOISE
    }
    tokens.discard("")
    return tokens


def _size_matches(listing_size: str, wanted: str) -> bool:
    """
    True when a listing's size answers to the size the user asked for.

    Whole tokens only, never substrings — `"s" in "us 9"` is True and so is
    `"l" in "xl"`, and both would hand back shoes to someone shopping for a
    small top.
    """
    tokens = _size_tokens(listing_size)
    # A one-size item fits whoever asked, so size never rules it out.
    if any(token.startswith("one size") for token in tokens):
        return True
    return bool(tokens & _size_tokens(wanted))


def _score(listing: dict, keywords: set[str]) -> int:
    """
    How well a listing overlaps the query keywords.

    A hit in the title, category, tags, colors, brand or platform is worth
    more than one buried in the description — those fields are what the item
    *is*. Plurals match in both directions, so "tee" finds "tees".
    """
    strong = (
        _words(listing["title"])
        | _words(listing["category"])
        | _words(listing.get("brand") or "")  # brand is None on most listings
        | _words(listing.get("platform") or "")
        | _words(" ".join(listing.get("style_tags") or []))
        | _words(" ".join(listing.get("colors") or []))
    )
    weak = _words(listing.get("description") or "")

    score = 0
    for keyword in keywords:
        forms = {keyword, keyword + "s"}
        if keyword.endswith("s"):
            forms.add(keyword[:-1])
        if forms & strong:
            score += 3
        elif forms & weak:
            score += 1
    return score


def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the listings data for items matching a description, and optionally a
    size and a price ceiling.

    This is the tool that doesn't call the model, which makes it the easiest one
    to test and the one to move onto MCP in unit 4.

    Args:
        description: keywords describing what the user wants
                     (e.g. "vintage graphic tee"). Scored against the title,
                     category, style tags, colors, brand, platform and
                     description of every listing that survives the filters.
        size:        a size string to filter by, or None to skip size filtering.
                     Matched case-insensitively on whole tokens, so "M" matches
                     "M", "M/L" and "S/M" but not "XL"; "W30" matches "W30 L30";
                     "US 9" matches "US 9" but not "US 8.5". Parenthetical notes
                     are ignored, so "XL" matches "XL (fits oversized)". A
                     listing sized "One Size" passes any size filter, because it
                     fits whoever asked.
        max_price:   maximum price, inclusive, or None to skip price filtering.

    Returns:
        A list of matching listing dicts, best match first — at most
        config.SEARCH_RESULT_LIMIT of them.
        **Returns an empty list when nothing matches — an empty list, not None,
        and not an exception.** Your loop branches on this.

        Nothing matching includes the case where `description` has no usable
        keywords: a listing has to score above zero on keyword overlap to come
        back at all, so a blank description matches nothing even when `size` and
        `max_price` would have let listings through.

    Each listing dict has these fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand (str or None), platform

    Note that `brand` is None for most listings. That is deliberate and
    realistic — thrift listings often have no brand.

    Test it from a terminal before you move on:
        python -c "from tools import search_listings; print(search_listings('graphic tee', max_price=30))"
    """
    keywords = {word for word in _words(description) if word not in _STOPWORDS}

    scored: list[tuple[int, dict]] = []
    for listing in load_listings():
        if max_price is not None and listing["price"] > max_price:
            continue
        if size is not None and not _size_matches(listing["size"], size):
            continue
        score = _score(listing, keywords)
        if score > 0:
            scored.append((score, listing))

    # Stable sort, so listings on the same score keep their order in the data.
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [listing for _, listing in scored[:config.SEARCH_RESULT_LIMIT]]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

# How the model should behave on both branches. This is the control surface:
# the format rules live here, and each branch adds its own rule about what the
# model is allowed to name.
_OUTFIT_SYSTEM = (
    "You are a styling assistant helping someone decide whether a second-hand "
    "find is worth buying. Be concrete and brief — plain sentences, no "
    "preamble, no sign-off, no markdown headings. Name actual garments rather "
    "than describing a vibe."
)

# The branch. With a wardrobe the model may only use what the user owns;
# without one it must not pretend to know what they own.
_WITH_WARDROBE = (
    " Build each outfit only from the wardrobe pieces listed in the prompt, "
    "plus the new item. Never invent a piece the user does not own, and refer "
    "to their pieces by the names given."
)
_WITHOUT_WARDROBE = (
    " The user has not entered a wardrobe, so you do not know what they own. "
    "Do not claim they own anything. Describe the kinds of pieces this item "
    "would pair with instead."
)


def _describe_item(item: dict) -> str:
    """The item's facts as prompt lines, with the missing ones left out."""
    price = item.get("price")
    facts = [
        f"Title: {item.get('title') or 'untitled listing'}",
        f"Category: {item.get('category') or 'unlisted'}",
        f"Size: {item.get('size') or 'unlisted'}",
        f"Condition: {item.get('condition') or 'unlisted'}",
        f"Colors: {', '.join(item.get('colors') or []) or 'unlisted'}",
        f"Style tags: {', '.join(item.get('style_tags') or []) or 'none'}",
        f"Price: ${price:.2f}" if isinstance(price, (int, float)) else "Price: unlisted",
        f"Platform: {item.get('platform') or 'unlisted'}",
    ]
    # brand is None on most listings, so it goes in only when it's really there.
    if item.get("brand"):
        facts.append(f"Brand: {item['brand']}")
    if item.get("description"):
        facts.append(f"Seller's description: {item['description']}")
    return "\n".join(facts)


def _describe_wardrobe(items: list[dict]) -> str:
    """The wardrobe as one line per piece, named the way the user named it."""
    lines = []
    for item in items:
        details = [item.get("category") or "uncategorised"]
        if item.get("colors"):
            details.append(", ".join(item["colors"]))
        if item.get("style_tags"):
            details.append(", ".join(item["style_tags"]))
        name = item.get("name") or item.get("id") or "unnamed piece"
        line = f"- {name} ({'; '.join(details)})"
        if item.get("notes"):
            line += f" — note: {item['notes']}"
        lines.append(line)
    return "\n".join(lines)


def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest one or two outfits.

    This one calls the model, through `generate()`. You don't need to think
    about rate limits — the adapter handles pacing for you.

    Args:
        new_item: a listing dict — the item the user is considering.
        wardrobe: a wardrobe dict with an 'items' key holding a list of items.
                  **It may be empty.** An empty wardrobe — or a missing 'items'
                  key, or None — takes the second branch below rather than
                  raising.

    Returns:
        A non-empty string with outfit suggestions.

        With a wardrobe: two outfits built only from pieces the user owns,
        named the way the user named them, with one line of reasoning each.

        With an empty wardrobe: general styling advice for the item instead —
        two or three ways to wear it, described by the kinds of pieces it pairs
        with, since there is nothing of the user's to name. Still a non-empty
        string. It does not raise and it does not return "".

    `ModelUnavailable` is left to propagate. The loop in agent.py is the layer
    that turns an unreachable model into a message for the user, and it already
    imports the exception to do it.

    Test it from a terminal before you move on:
        python -c "from tools import suggest_outfit; from utils.data_loader import get_example_wardrobe, load_listings; print(suggest_outfit(load_listings()[0], get_example_wardrobe()))"
    """
    item = new_item or {}
    items = (wardrobe or {}).get("items") or []
    item_block = _describe_item(item)

    if items:
        system = _OUTFIT_SYSTEM + _WITH_WARDROBE
        prompt = (
            "Here is a second-hand item someone is considering:\n\n"
            f"{item_block}\n\n"
            f"Here is everything in their wardrobe ({len(items)} pieces):\n\n"
            f"{_describe_wardrobe(items)}\n\n"
            "Suggest two outfits pairing the new item with pieces from that "
            "wardrobe. Name the pieces in each, and give a single sentence on "
            "why it works. If the new item clashes with everything they own, "
            "say so plainly in one line and then give the closest two outfits "
            "anyway."
        )
    else:
        system = _OUTFIT_SYSTEM + _WITHOUT_WARDROBE
        prompt = (
            "Here is a second-hand item someone is considering:\n\n"
            f"{item_block}\n\n"
            "They have not entered a wardrobe, so you cannot build outfits "
            "from what they own. Give general styling advice for this item "
            "instead: two or three ways to wear it, each naming the kinds of "
            "pieces it would pair with, plus one line on the look it suits."
        )

    reply = generate(prompt, system=system).strip()
    if not reply:
        # generate() can hand back an empty string. The contract above promises
        # non-empty, and the loop feeds this straight into create_fit_card.
        colors = ", ".join(item.get("colors") or []) or "neutrals"
        title = item.get("title") or "this item"
        return (
            f"No styling ideas came back for {title}. Try again, or build "
            f"around its colors: {colors}."
        )
    return reply


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

# A caption, not a product listing. The sentence count and the "mention the
# price and platform once" rule live here because they are the shape of the
# output, not part of any one item.
_FIT_CARD_SYSTEM = (
    "You write the caption a person posts with a thrift find. Write the way "
    "someone posts — first person, casual, specific about the look. Two to "
    "four sentences, one paragraph, no headings, no preamble, at most one "
    "hashtag. Mention the price once and the platform once. Do not repeat the "
    "listing title word for word, and do not write like a shop description."
)


def _item_line(item: dict) -> str:
    """One plain sentence of the item's facts, for the no-outfit branch."""
    price = item.get("price")
    details = []
    if item.get("size"):
        details.append(f"size {item['size']}")
    if item.get("condition"):
        details.append(f"{item['condition']} condition")
    where = " ".join(
        part for part in (
            f"${price:.2f}" if isinstance(price, (int, float)) else "",
            f"on {item['platform']}" if item.get("platform") else "",
        ) if part
    )
    if where:
        details.append(where)

    title = item.get("title") or "This find"
    return f"{title}, {', '.join(details)}" if details else title


def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Write a short caption someone would actually post about the find.

    This calls the model too.

    Args:
        outfit:   the outfit suggestion string from suggest_outfit().
        new_item: the listing dict for the item.

    Returns:
        A two-to-four sentence caption.

        If `outfit` is empty, whitespace-only or None, it returns a plain
        description of the item instead — what it is, its size, condition,
        price and platform, and the fact that no outfit came through. That
        branch does **not** call the model and says nothing about how the item
        would be worn, because there is nothing to say it from. It does not
        raise.

    The caption reads like a real post rather than a product description,
    mentions the item, its price and its platform once each, and is specific
    about the vibe. Those rules are in _FIT_CARD_SYSTEM.

    It should also come out **differently for different inputs** — and on
    repeated runs of the *same* input. If three runs give three identical
    strings, it is one of two things, both near the top of `config.py`:

        • CACHE_ENABLED — the adapter handed back an answer it already had.
          It is True by default, so repeating one input while building is
          *expected* to return the same words. `run_eval.py` turns it off.
        • TEMPERATURE — at 0.0 the model gives the same words every time.
          It is 0.9 here, which is what makes the variation possible once the
          cache is out of the way.

    Test it from a terminal before you move on:
        python -c "from tools import create_fit_card; from utils.data_loader import load_listings; print(create_fit_card('jeans and white sneakers', load_listings()[0]))"
    """
    item = new_item or {}

    # The branch: no outfit means no caption to write. Describe the item and
    # stop, rather than inventing a look nobody suggested.
    if not (outfit or "").strip():
        return (
            f"{_item_line(item)}. No outfit suggestion came through for this "
            f"find, so there is no caption to go with it yet."
        )

    prompt = (
        "Here is the find:\n\n"
        f"{_describe_item(item)}\n\n"
        "Here is how it is being styled:\n\n"
        f"{outfit.strip()}\n\n"
        "Write the caption the buyer would post about this find."
    )

    reply = generate(prompt, system=_FIT_CARD_SYSTEM).strip()
    if not reply:
        # Same reason as in suggest_outfit: the contract promises a string with
        # something in it, and this is the last thing the loop returns.
        return (
            f"{_item_line(item)}. No caption came back from the model for this "
            f"one — worth another try."
        )
    return reply
