# Dataset

The HHGR system uses multiple datasets for ingestion, hierarchy parsing, knowledge graph construction, and evaluation.

## Corpus Documents

### Indian Contract Act, 1872 (Primary Evaluation Corpus)

- **Document ID:** `0d1934142f67c5f5`
- **Hierarchy File:** `data/hierarchy/0d1934142f67c5f5.json`
- **Total Nodes:** 222
- **Section Nodes:** 192
- **Total Edges:** 233
- **Hierarchy Depth:** Document → Chapter → Section → Clause
- **Node Types:** document, chapter, section, clause, explanation, illustration, proviso, schedule

This document is the primary corpus for evaluation. The parser extracts the full hierarchical structure of the Indian Contract Act including all chapters, sections, clauses, explanations, illustrations, and provisos.

### Full Document Collection

- **Hierarchy JSONs:** 207 files in `data/hierarchy/`
- **Processed JSONs:** 1156 files in `data/processed/`
- **Provenance JSONs:** 140 files in `data/provenance/`
- **Uploaded PDFs:** 13 files in `data/uploads/`

## Evaluation Datasets

### Benchmark CSV (`data/eval/contract_act_1872_benchmark.csv`)

A 50-question benchmark covering the Indian Contract Act, 1872.

| Field | Description |
|-------|-------------|
| ID | Unique question identifier (ICA1872-001 to ICA1872-050) |
| Question | Natural language legal question |
| Query_Type | Category: definition, section_lookup, comparison, procedure, explanation, scenario |
| Difficulty | Easy, Medium, or Hard |
| Expected_Section | Section number(s) the answer should reference |
| Expected_Keywords | Key terms that should appear in retrieved evidence |
| Expected_Answer_Summary | Brief description of the correct answer |

**Distribution by Query Type:**

| Query Type | Count | Description |
|------------|-------|-------------|
| definition | 8 | "What is a contract?" |
| section_lookup | 10 | "Which section defines consideration?" |
| comparison | 8 | "How do Sections 23 and 24 differ?" |
| procedure | 8 | "How is a contract rescinded?" |
| explanation | 8 | "Explain the doctrine of privity" |
| scenario | 8 | "If A promises B..." (hypotheticals) |

**Distribution by Difficulty:**

| Difficulty | Count | Description |
|------------|-------|-------------|
| Easy | 17 | Direct fact lookup, single section |
| Medium | 17 | Multi-section reasoning, definitions |
| Hard | 16 | Cross-references, scenarios, comparisons |

### Gold Standard Dataset (`data/eval/gold/`)

34 evaluation items across 5 Indian legal domains.

#### Contract Act Gold (`contract_act_gold.json`)

- **Items:** 10 (ica-001 through ica-010)
- **Grounded:** Yes (node-level relevance labels)
- **Languages:** English + Hindi (ica-006)
- **Test Types:** Direct fact lookup, definitions, hierarchy traversal, reverse-phrased, multilingual, two-part conditional

#### BNS Gold (`bns_gold.json`)

- **Items:** 6 (bns-001 through bns-006)
- **Domain:** Bharatiya Nyaya Sanhita, 2023
- **Grounded:** No (citation-string matched)
- **Topics:** Murder punishment, offence definition, theft, private defence, criminal breach of trust, repeal of IPC

#### BNSS Gold (`bnss_gold.json`)

- **Items:** 6 (bnss-001 through bnss-006)
- **Domain:** Bharatiya Nagarik Suraksha Sanhita, 2023
- **Grounded:** No (citation-string matched)
- **Topics:** Arrest information, electronic evidence, custody, trial in absence, undertrial release, FIR filing

#### BSA Gold (`bsa_gold.json`)

- **Items:** 6 (bsa-001 through bsa-006)
- **Domain:** Bharatiya Sakshya Adhiniyam, 2023
- **Grounded:** No (citation-string matched)
- **Topics:** Relevant facts, electronic records, document definition, dying declarations, secondary evidence, witness competency

#### SC Judgments Gold (`sc_judgments_gold.json`)

- **Items:** 6 (sc-001 through sc-006)
- **Domain:** Supreme Court of India judgments
- **Grounded:** No (citation-string matched)
- **Cases:** Har Bhajan Lal, Balfour v. Balfour, Carlill v. Carbolic Smoke Ball, Satya Brat Ghose, D.K. Basu, Anvar P.V.

## Gold Item Schema

Each gold item follows this structure:

```json
{
  "id": "ica-001",
  "domain": "contract_act",
  "language": "en",
  "grounded": true,
  "difficulty": "easy",
  "query": "What is the definition of a contract under the Indian Contract Act?",
  "reference_answer": "A contract is defined under Section 2(h) as an agreement enforceable by law.",
  "citations": [
    {
      "node_id": "section_2h",
      "label": "Section 2(h)",
      "numbering": "2(h)",
      "title": "Definition of Contract"
    }
  ],
  "expected_counter_authority_markers": [],
  "notes": "Direct definition lookup"
}
```

## Hierarchy Node Statistics

### Primary Corpus (0d1934142f67c5f5)

| Metric | Value |
|--------|-------|
| Total Nodes | 222 |
| Section Nodes | 192 |
| Document Nodes | 1 |
| Chapter Nodes | ~10 |
| Clause Nodes | ~19 |
| Total Edges | 233 |
| Edge Types | PART_OF, CITES, REFERENCES |

### Before Parser Fix

| Metric | Before | After |
|--------|--------|-------|
| Total Nodes | 46 | 222 |
| Section Nodes | 16 | 192 |
| Sections as Standalone | 6 (phantom) | 192 (real) |

The parser fix expanded the hierarchy from 46 to 222 nodes by properly detecting embedded sections (e.g., "Section 14 — What agreements are contracts" within "Chapter II").

## Provenance Data

- **Directory:** `data/provenance/`
- **Files:** 99 JSON files
- **Content:** Query-response provenance records with retrieval stages, confidence scores, evidence chunks, and reasoning chains
- **Format:** Keyed by `provenance_id`, each containing full query context, retrieved evidence, generated answer, and verification results
