# Invoice calendar and status evidence policy

This is a bounded deterministic extraction policy, not payment authorization,
universal document understanding, model evaluation or production qualification.
The authorized preview remains explicit input, review and manual copy.

## Calendar admission

- Dates must parse as complete Gregorian dates, including leap-year and
  leap-century validation. Invalid dates have no raw-text fallback.
- Supported forms are year-first numeric dates, English month-name dates and
  day-first slash dates only when the first component exceeds 12.
- Numeric dates with both first components at most 12 abstain, including equal
  components. No locale is inferred and US month-first syntax is not assumed.
- Recognized invalid, ambiguous or conflicting candidates block only their
  labeled field; an issue-date problem does not invalidate a separate due date.
  Invalid candidates must not be discarded to select a convenient valid one.
- Returned evidence spans remain literal source text with supporting chunk IDs.

The baseline emitted impossible dates such as `2026-02-31` and `April 31, 2026`,
and retained ambiguous `03/04/2026`. These are extraction defects, not valid
obligations. Unsupported date syntax is not a promise of contradiction detection.

## Document status

Bounded English invoice headers, status labels and explicit amount/total warnings
can make a document nonfinal and suppress a payable total across chunks. A later
`FINAL` label must not silently override contradictory nonfinal evidence. Qualified
invoice headers establish context but are not vendor names. Incidental vendor,
item or prose words and negated status phrases must not trigger keyword-only
suppression.

This policy assumes one invoice across the supplied chunks. It does not segment
multiple invoices, classify every language or interpret unrestricted prose. Independent
review caught eight unsafe-total regressions in an intermediate narrower grammar.
The released revision closes those eight cases and preserves tested incidental-word
and negation controls. Unsupported punctuation and warning forms can remain outside
this bounded policy; absence of a recognized warning is not approval to pay.

## Evidence and release boundary

Focused parser tests establish only their tested contracts. Historical selected
seven-document benchmark observations remain recorded separately in
[Release qualification](RELEASE_QUALIFICATION.md); they are not population accuracy
or real-model measurements. Neither deterministic success nor a source citation
makes an extracted amount safe to pay. Human review remains required.
