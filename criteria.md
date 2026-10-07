# Acceptance criteria — FitFindr

Five criteria that say what "working" means for this agent, written in unit 3
**before** any results existed.

An acceptance criterion names a target: a number, a count, a rate, or something
a person could plainly observe. *"The agent handles errors"* is an opinion.
*"When search returns nothing, the agent stops before calling the second tool,
in 5 of 5 tries"* is a criterion.

Under each one, write a sentence or two on **why that target** and not a
stricter one. A reason that says something about your tools, your loop, or the
data earns credit; *"80% seemed reasonable"* does not.

> Missing your own targets next unit costs you nothing. Setting a target so
> easy you can't miss it does.

**Two are written for you. You write three.**

---

## 1. A matching query completes all three tools

Given a query that matches at least one listing, the agent completes all three
tool calls and returns a fit card — in at least 4 of 5 tries.

**Why this target:**

My search is a plain keyword match and some phrasing will miss.

---

## 2. An impossible query stops before the second tool

Given a query that matches no listings, the agent stops before calling
`suggest_outfit` and returns a message naming what to change — 5 of 5 tries.

**Why this target:**
This path must execute this way since the agent must follow the branch rule, stopping after search_listings.

---

## 3. Something about state

Across 5 matching queries, the id in session["selected_item"] is the same id that appears in the suggest_outfit trace line's inputs - 5 / 5.



**Why this target:**
The two independent records agreeing indicates that the suggest_outfit tool referenced the actual selected item by the user and not something else.



---

## 4. Something about the fit card

Given an empty or whitespace only outfit, the agent does not mention anything about how the item fits into an outfit in 5 of 5 tries.



**Why this target:**
It is expected behavior that the agent is able to differentiate between the presence and lack of an outfit so the creteria is all 5 tries of 5.



---

## 5. Your choice

The results of a search have a price that is less than or equal to the provided max_price in 5 of 5 tries given that a max_price is provided.


**Why this target: The tool's output is not useful if the user entered in a max price that is subsequently ignored, so it is set to 5 of 5 tries.**


---

<!-- ─────────────────────────────────────────────────────────────────────────
     UNIT 4 — read this before you change anything above.

     If a criterion turns out to be BROKEN rather than merely unmet, you can
     revise it, and that earns credit. But never delete or edit the original
     line. Add the revision underneath it, like this:

         ## 4. Something about the fit card

         The fit card is different every time.

         **Why this target:** ...

         > **Revised in unit 4:** For 5 different items, the 5 fit cards share
         > no opening sentence.
         >
         > **Why revised:** "different" wasn't checkable — two cards that
         > differed by one word still counted. The new version is something I
         > can actually score.

     That's a revision because the criterion couldn't be MEASURED.

     Lowering a target because you missed it is not a revision, and it costs
     you the point:

         ✗ "I said the empty search stops it 5 of 5 times, but I got 3 of 5,
            so 3 of 5 is more realistic."

     A number you missed stays where it is, gets diagnosed, and gets a fix
     attempted. That's where the points are.
     ───────────────────────────────────────────────────────────────────────── -->
