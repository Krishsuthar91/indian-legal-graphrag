# HHGR v1.0.0 — Release Notes

## Hybrid Hierarchical Graph Retrieval for Indian Legal Document Intelligence

This is the **initial public release** of HHGR: an explainable, multilingual question-answering system for Indian legal documents.

### What's Included

**Retrieval Engine**
- Four-signal hybrid retrieval: lexical (0.30), citation (0.20), hierarchy (0.30), structural (0.20)
- Dense + graph + hierarchy fusion with configurable weights (0.40 / 0.35 / 0.25)
- Multilingual dense search over Qdrant (bge-m3, LaBSE, MuRIL, IndicBERT)

**Legal Parsing**
- Stack-based hierarchy parser with 20+ numbering patterns
- Document → Chapter → Section → Clause extraction
- Nested Set Index for fast subtree queries

**Verification Framework**
- 12-component pipeline: evidence sufficiency, relevance, citation entailment, verification badge, confidence calibration
- Structured audit traces with full provenance
- Grounding guard that returns deterministic fallbacks when evidence is insufficient

**Full-Stack Application**
- FastAPI backend with 11 REST endpoints
- React 18 + TypeScript dashboard (Cytoscape, React Flow, Recharts)
- 6-service Docker Compose stack (api, react, nginx, neo4j, qdrant, redis)
- Prometheus/Grafana monitoring, API key auth, rate limiting

### Benchmark Results

Deterministic offline benchmark (50 questions, mock LLM, seed 42):

| Metric | Value |
|--------|-------|
| Overall Score | **0.6271** |
| Section Accuracy | **0.8700** |
| MRR | **0.7400** |
| Grounding Accuracy | **1.0000** |
| Avg Latency | **108ms** |

*Answer-related metrics (hallucination rate, faithfulness) reflect the mock LLM's grounding behaviour and are documented as such.*

### Installation

```bash
git clone https://github.com/Krishsuthar91/indian-legal-graphrag.git
cd indian-legal-graphrag
pip install -r requirements.txt
cp .env.example .env
uvicorn src.main:app --reload
```

### Docker

```bash
docker compose up --build
```

### Testing

- **908 backend tests** (pytest)
- **49 frontend tests** (Vitest)
- `ruff check src/` clean

### Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [API Reference](docs/API.md)
- [Evaluation](docs/Evaluation.md)
- [Verification Framework](docs/VerificationFramework.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Developer Guide](docs/DEVELOPER.md)

### License

MIT License
