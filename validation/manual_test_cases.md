# HHGR Legal QA — Manual Validation Suite

End-to-end manual acceptance tests that exercise the entire HHGR pipeline exactly
as a user would: query → retrieval → evidence ranking → relevance judge →
sufficiency → confidence → verification badge → grounding guard → LLM answer.

These are **not** unit tests. Each row is a full pipeline run hit through the
local FastAPI `/query` endpoint. A mechanical runner (`run_manual_validation.py`)
executes every case, compares the live response against the expectations in
`expected_results.json`, and writes `validation_report.md`.

Expected-value reference conventions:

- `expected_section`: the section number that must appear in the **top** retrieved
  evidence (canonical Indian Contract Act, 1872, document `0d1934142f67c5f5`).
- `expected_status`: the verification status that must be returned
  (`supported` = grounded answer allowed, `insufficient` = grounded-guard block).
- `confidence_min` / `confidence_max`: accepted confidence window.
- `blocked`: whether the grounding guard must suppress the LLM answer.
- `wrong_document_tolerated`: some concept queries legitimately pull IPC clutter;
  `false` marks cases where any wrong-document top-1 is a failure.

---

## Category 1 — Direct section lookup

`expected_*`: exact-matching Section should surface, `0d1934142f67c5f5`.

| # | Query | Expected section | Expected status |
|---|-------|------------------|-----------------|
| 1.001 | What is Section 1? | 1 | supported |
| 1.002 | What is Section 2? | 2 | supported |
| 1.003 | Explain Section 3. | 3 | supported |
| 1.004 | Explain Section 4. | 4 | supported |
| 1.005 | What does Section 5 state? | 5 | supported |
| 1.006 | What is Section 6? | 6 | supported |
| 1.007 | Explain Section 7. | 7 | supported |
| 1.008 | What does Section 8 state? | 8 | supported |
| 1.009 | Explain Section 9. | 9 | supported |
| 1.010 | What is Section 10? | 10 | supported |
| 1.011 | The essentials of Section 10 | 10 | supported |
| 1.012 | Explain Section 11. | 11 | supported |
| 1.013 | What does Section 12 state? | 12 | supported |
| 1.014 | What is Section 13? | 13 | supported |
| 1.015 | Explain Section 14. | 14 | supported |
| 1.016 | What is Section 15? | 15 | supported |
| 1.017 | What does Section 16 state? | 16 | supported |
| 1.018 | Explain Section 17. | 17 | supported |
| 1.019 | What is Section 18? | 18 | supported |
| 1.020 | Explain Section 19. | 19 | supported |
| 1.021 | What does Section 20 state? | 20 | supported |
| 1.022 | What is Section 23? | 23 | supported |
| 1.023 | Explain Section 25. | 25 | supported |
| 1.024 | What does Section 27 state? | 27 | supported |
| 1.025 | What is Section 37? | 37 | supported |
| 1.026 | Explain Section 56. | 56 | supported |
| 1.027 | What does Section 65 state? | 65 | supported |
| 1.028 | What is Section 72? | 72 | supported |
| 1.029 | Explain Section 73. | 73 | supported |
| 1.030 | What does Section 74 state? | 74 | supported |
| 1.031 | What is Section 124? | 124 | supported |
| 1.032 | Explain Section 126. | 126 | supported |
| 1.033 | What does Section 128 state? | 128 | supported |
| 1.034 | What is Section 148? | 148 | supported |
| 1.035 | Explain Section 171. | 171 | supported |
| 1.036 | What does Section 172 state? | 172 | supported |
| 1.037 | What is Section 182? | 182 | supported |
| 1.038 | Explain Section 185. | 185 | supported |
| 1.039 | What does Section 188 state? | 188 | supported |
| 1.040 | What is the short title and commencement? | 1 | supported |
| 1.041 | How is a contract defined? | 2 | supported |

## Category 2 — Concept lookup

`expected_status` reflects the defining section for a concept.

| # | Query | Expected section | Expected status |
|---|-------|------------------|-----------------|
| 2.001 | What is coercion? | 15 | supported |
| 2.002 | What is fraud? | 17 | supported |
| 2.003 | What is consideration? | 2 | supported |
| 2.004 | What is free consent? | 14 | supported |
| 2.005 | What is an offer? | 2 | supported |
| 2.006 | What is a proposal? | 2 | supported |
| 2.007 | What is undue influence? | 16 | supported |
| 2.008 | What is misrepresentation? | 18 | supported |
| 2.009 | What is consent? | 13 | supported |
| 2.010 | What is a contract? | 2 | supported |
| 2.011 | What is an agreement? | 2 | supported |
| 2.012 | What is a promise? | 2 | supported |
| 2.013 | What is voidability? | 19 | supported |
| 2.014 | What is a contingent contract? | 31 | supported |
| 2.015 | What is a wagering agreement? | 30 | supported |
| 2.016 | What is a guarantee? | 126 | supported |
| 2.017 | What is an indemnity? | 124 | supported |
| 2.018 | What is bailment? | 148 | supported |
| 2.019 | What is a pledge? | 172 | supported |
| 2.020 | What is an agency? | 182 | supported |
| 2.021 | What is a minor's capacity to contract? | 11 | supported |
| 2.022 | What is a mistake of fact? | 20 | supported |
| 2.023 | What is a restraint of trade? | 27 | supported |
| 2.024 | What is the liability of a finder of goods? | 71 | supported |

## Category 3 — Relationship questions

| # | Query | Expected section | Expected status |
|---|-------|------------------|-----------------|
| 3.001 | Difference between void agreement and voidable contract. | 2 | supported |
| 3.002 | Difference between proposal and acceptance. | 2 | supported |
| 3.003 | Difference between fraud and misrepresentation. | 17 | supported |
| 3.004 | Difference between coercion and undue influence. | 15 | supported |
| 3.005 | Difference between a promise and an agreement. | 2 | supported |
| 3.006 | Difference between indemnity and guarantee. | 124 | supported |
| 3.007 | Difference between bailment and pledge. | 148 | supported |
| 3.008 | Difference between agent and servant. | 182 | supported |
| 3.009 | How does void differ from voidable? | 2 | supported |
| 3.010 | What is the relationship between offer and acceptance? | 2 | supported |

## Category 4 — Scenario questions

| # | Query | Expected section | Expected status |
|---|-------|------------------|-----------------|
| 4.001 | A person receives money by mistake, can it be retained? | 72 | supported |
| 4.002 | A contract signed under threats, is it valid? | 15 | supported |
| 4.003 | An agreement without consideration, is it valid? | 25 | supported |
| 4.004 | Both parties are under a mistake as to a matter of fact, is the agreement valid? | 20 | supported |
| 4.005 | An agreement in restraint of trade, is it valid? | 27 | supported |
| 4.006 | A promise to pay money won by wager, is it enforceable? | 30 | supported |
| 4.007 | A contract contingent on an impossible event, is it valid? | 36 | supported |
| 4.008 | A person pays money owed by another to save his own interest, can he recover it? | 69 | supported |
| 4.009 | A bailee loses goods entrusted to him, is he liable? | 151 | supported |
| 4.010 | A surety is discharged by a variance, what is the effect? | 133 | supported |
| 4.011 | A party fails to perform on time under a fixed-time contract, what happens? | 55 | supported |
| 4.012 | A person refuses to perform his promise wholly, what is the consequence? | 39 | supported |
| 4.013 | An agent exceeds his authority, is the principal bound? | 227 | supported |
| 4.014 | A buyer receives goods but does not pay the agreed price, is a suit maintainable? | 4 | supported |
| 4.015 | A contract is rescinded as voidable, must the party restore the benefit? | 64 | supported |

## Category 5 — Adversarial queries

`expected_status`: `insufficient` and `blocked` when the provision is not indexed.

| # | Query | Expected section | Expected status | Blocked |
|---|-------|------------------|-----------------|---------|
| 5.001 | Section 999 | none | insufficient | true |
| 5.002 | Section 420 IPC | none | insufficient | true |
| 5.003 | Section 420 Contract Act | none | insufficient | true |
| 5.004 | What is Section 300 of the Indian Penal Code? | none | insufficient | true |
| 5.005 | Explain Section 9999. | none | insufficient | true |
| 5.006 | Section 0 | none | insufficient | true |
| 5.007 | Section -5 | none | insufficient | true |
| 5.008 | What is Section 999 of the IPC? | none | insufficient | true |
| 5.009 | Is there a Section 999 in the Contract Act? | none | insufficient | true |
| 5.010 | Define the "theft of incorporeal land". | none | insufficient | true |
| 5.011 | Explain the doctrine of "quantum teleportation of contracts". | none | insufficient | true |
| 5.012 | What is the "gnome clause" of the Contract Act? | none | insufficient | true |
| 5.013 | qqxwv zzznope unrelated gibberish | none | insufficient | true |
| 5.014 | asdkjh 12321 plqw asdfzxcv | none | insufficient | true |
| 5.015 | xyzzy plugh foobar wibble | none | insufficient | true |
| 5.016 | What colour is the evidence? | none | insufficient | true |
| 5.017 | Section 420B of an act that does not exist | none | insufficient | true |
| 5.018 | Explain Section 999 of the Indian Contract Act, 1872. | none | insufficient | true |
| 5.019 | How many sections does the Contract Act contain that are not in it? | none | insufficient | true |
| 5.020 | What does Section eight hundred apply to? | none | insufficient | true |

## Category 6 — Hallucination prevention (out-of-corpus statutes)

`blocked` true whenever the statute is not present in the indexed corpus.

| # | Query | Expected status | Blocked |
|---|-------|-----------------|---------|
| 6.001 | What is the punishment under the United States Bankruptcy Code Chapter 11? | insufficient | true |
| 6.002 | Explain the Australian Consumer Law section on unfair terms. | insufficient | true |
| 6.003 | What does the UK Companies Act 2006 Section 172 require? | insufficient | true |
| 6.004 | Explain Article 14 of the Indian Constitution? | insufficient | true |
| 6.005 | What does the GDPR Article 17 say? | insufficient | true |
| 6.006 | Explain Section 302 of the Criminal Procedure Code (CrPC) of India. | insufficient | true |
| 6.007 | What is the California Civil Code Section 1542? | insufficient | true |
| 6.008 | Explain the German Civil Code (BGB) Section 433. | insufficient | true |
| 6.009 | What does the New York General Obligations Law Section 5-701 state? | insufficient | true |
| 6.010 | Explain the Paris Convention Article 4bis. | insufficient | true |
| 6.011 | What does the Reserve Bank of India's Master Direction on KYC say? | insufficient | true |
| 6.012 | Explain Section 12 of the Central Goods and Services Tax Act, 2017. | insufficient | true |
| 6.013 | What is the fine under the Motor Vehicles Act, 1988 Section 183? | insufficient | true |
| 6.014 | Explain the Arbitration and Conciliation Act, 1996 Section 34. | insufficient | true |
| 6.015 | What does the Income Tax Act, 1961 Section 80C permit? | insufficient | true |
| 6.016 | Explain the Limitation Act, 1963 Section 3. | insufficient | true |
| 6.017 | What does the Specific Relief Act, 1963 Section 10 require? | insufficient | true |
| 6.018 | Explain the Partnerships Act, 1932 Section 69. | insufficient | true |
| 6.019 | What does the Negotiable Instruments Act, 1881 Section 138 state? | insufficient | true |
| 6.020 | Explain the Employees' Provident Funds Act, 1952 Section 14. | insufficient | true |

---

## How to run

```bash
python validation/run_manual_validation.py
```

The runner builds the in-memory corpus once, injects a deterministic mock LLM
(reproducible offline), and issues every case through the FastAPI `/query`
endpoint. Results are compared to `expected_results.json` and summarized in
`validation_report.md`.

## Interpreting failures

- A `supported` case marked `blocked` → grounding guard is rejecting grounded
  evidence (false positive), a retrieval/confidence regression.
- An `insufficient` case that returns `supported` and a real answer → the guard
  failed to block a fabricated/out-of-score answer (hallucination risk).
- `wrong document` top-1 (e.g. an IPC node when an ICA section was expected,
  with `wrong_document_tolerated=false`) → cross-document retrieval noise.
