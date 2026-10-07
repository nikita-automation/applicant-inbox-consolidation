# Design notes

## Why not just match on e-mail?

Because the data does not cooperate. On the sample alone: one person applies with two different e-mail addresses
(matched by phone), another writes `Clara Mueller` on the form and `Clara Müller` on a job board, a third sends
a chat message that contains nothing but a phone number. Matching on one raw field misses all of them — and
matching on *any* shared field merges strangers (a family phone, an agency mailbox).

## The matching rule

> Link two applications if they share a normalised e-mail **or** a normalised phone number, **and** their names
> are *compatible*. Join the links transitively.

**Compatible** means: one name's tokens are contained in the other's, where a single letter counts as an initial
and a missing name never contradicts anything.

| A | B | Compatible |
|---|---|---|
| Anna Beispiel | A. Beispiel | yes (initial) |
| Anna Beispiel | Beispiel, Anna-Lena | yes (subset, order ignored) |
| Clara Müller | Clara Mueller | yes (umlauts spelled out) |
| Hasan Beispielmann | BEISPIELMANN, Hasan | yes |
| *(no name)* | anything | yes — a chat message carries only a number |
| Ida Muster | Jan Muster | **no** |
| Felix Fiktiv | Franka Fiktiv | **no** |

The name check is deliberately *weak* (containment, not similarity score): a false merge of two people is worse
than a missed duplicate, and the missed ones surface in the report anyway.

## Why transitive, and what that costs

Union-find makes the result independent of import order (tested with random shuffles) and lets a three-channel
applicant collapse into one candidate. The price: a **nameless** record can bridge two people who share a
contact — e.g. a chat message from a number that both `Ida Muster` and `Jan Muster` gave. The group is kept,
but flagged `needs_review`, because pairwise name checks passed while the group as a whole contradicts itself.

## Normalisation decisions

- **Phones:** to `+<country><digits>`. Handles national format, `00` prefix, `+49 (0) …` and the typo `+49 0151…`.
  Anything that cannot be read as a number (`n/a`, `123`, a local number without area code) becomes empty — a wrong
  guess would create false merges.
- **E-mail:** lower-case and trim only. Removing dots or `+tags` is valid for some providers and wrong for others.
- **Names:** `ä→ae, ö→oe, ü→ue, ß→ss`, then accents stripped, titles dropped, `Last, First` reordered.
- **Phone in free text:** only numbers with a label (`Tel.`, `Mobil`) or a leading `+`. A bare digit run would turn
  `05.10.2026` into a phone number.
- **Time:** stored as UTC; naive timestamps are read as `Europe/Berlin`.

## Data model

- `applications` — immutable facts as received: normalised *and* raw contact values, `UNIQUE(source, source_id)`.
- `candidates` — **derived** data, rebuilt by every `merge`. Because nothing refers to a candidate row, the
  merge rules can be improved at any time without a migration.
- `candidate_id` is derived from the *earliest* member application, so it stays the same when later duplicates
  attach to the person.

## Idempotency

Every adapter needs a stable `source_id`: the channel's own id where there is one, the `Message-ID` for mail, a
content hash for chat lines. Re-importing a full export (the normal way to "catch up") therefore only adds what
is new.

## Error handling

An unreadable row becomes an entry in `ParseResult.errors` with its position and the reason; the rest of the
file is imported. The CLI prints the count per channel so a silently dropped batch is impossible to miss.

## Known limits / next steps

- Blocking index instead of pairwise comparison inside a shared-contact bucket (for very large inboxes).
- A fuzzy name score for the *possible duplicates* list (today: identical normalised full name).
- Review decisions (`merge` / `keep apart`) stored per pair so a human only answers once.
- Real connectors (IMAP polling, webhook receiver) in front of the adapters — the adapters already take plain
  files, which is what such a connector would drop into a folder.
