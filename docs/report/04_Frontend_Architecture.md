# 04 — Frontend Architecture

The frontend is a **React 18 + TypeScript** single-page application ("explain-ui", v1.0.0)
located in `ui/`. It serves as the primary user interface for asking legal questions,
inspecting evidence, exploring the legal knowledge graph and hierarchy, uploading documents,
and reviewing persisted provenance.

Primary sources: `ui/package.json`, `ui/vite.config.ts`, `ui/src/main.tsx`, `ui/src/App.tsx`,
and the `ui/src/{pages,components,hooks,api,types,utils}/` folders.

---

## 4.1 Technology stack

| Concern | Choice | Evidence |
|---------|--------|----------|
| UI library | React 18 | `ui/package.json` |
| Language | TypeScript ~5.6.3 | `ui/package.json`, `ui/tsconfig.json` |
| Build tool | Vite 5 | `ui/vite.config.ts` |
| Styling | Tailwind CSS 3 | `ui/tailwind.config.js`, `ui/postcss.config.js` |
| Server state | `@tanstack/react-query` v5 (backed by `axios`) | `ui/src/hooks/`, `ui/src/api/client.ts` |
| Routing | `react-router-dom` v6 (`BrowserRouter`) | `ui/src/App.tsx` |
| Knowledge-graph view | Cytoscape.js | `ui/src/components/KnowledgeGraph.tsx` |
| Hierarchy view | `@xyflow/react` (React Flow) | `ui/src/components/HierarchyTree.tsx` |
| Charts | Recharts (confidence gauge) | `ui/src/components/ConfidenceGauge.tsx` |
| Motion | `framer-motion` | `ui/src/components/` |
| Testing | Vitest (+ jsdom) | `ui/vite.config.ts`, `ui/src/**/*.test.ts` |

---

## 4.2 Application bootstrap

`ui/src/main.tsx` mounts `<App />` into `#root` wrapped in the providers.

`ui/src/App.tsx` defines:

- A single **`QueryClient`** (`@tanstack/react-query`) with sensible defaults (retries,
  `staleTime`) provided via `QueryClientProvider`.
- **`BrowserRouter`** with the application shell (header/nav/sidebar) and `<Routes>`.
- A dark/light theme provider driven by the settings hook.

---

## 4.3 Routing / pages

Five pages under `ui/src/pages/`:

| Route | Page | Purpose |
|-------|------|---------|
| `/` | `Home.tsx` | Landing page, example legal queries, feature overview |
| `/explain` | `Explain.tsx` | Main QA workspace: question input, answer, evidence, KG, hierarchy, confidence, provenance |
| `/upload` | `Upload.tsx` | Upload PDF/DOCX/TXT, watch indexing, trigger pipeline |
| `/provenance` (and `/provenance/:id`) | `Provenance.tsx` | Browse/re-load persisted provenance records by id |
| `/settings` | `Settings.tsx` | API base URL, theme, display preferences, LLM/provider info |

Navigation uses `react-router-dom` `<Link>`/`useNavigate`; the shell persists across routes.

---

## 4.4 Component library (14 components)

Components live in `ui/src/components/` and are composed by the pages:

| Component | Role |
|-----------|------|
| `AnswerCard.tsx` | Renders the generated answer with inline numbered citations and the verification badge |
| `QueryInput.tsx` | Question textarea + submit; validates and triggers the query mutation |
| `EvidencePanel.tsx` | Lists retrieved evidence units (section number, title, snippet, scores) |
| `EvidenceCard.tsx` | Single evidence item with per-signal score breakdown |
| `ConfidenceGauge.tsx` | Recharts radial gauge of the composite confidence score |
| `KnowledgeGraph.tsx` | Cytoscape graph of the retrieved sub-graph (`PART_OF`/`CITES` edges) |
| `HierarchyTree.tsx` | React Flow tree of Document→Chapter→Section→Clause with the active path highlighted |
| `CitationList.tsx` | Numbered citations with links to source sections |
| `ProvenancePanel.tsx` | Ranking signals, hierarchy paths, counter-authority markers, verification trace |
| `ReasoningChain.tsx` | Step-by-step reasoning chain (sufficiency → retrieval → verification → generation) |
| `VerificationBadge.tsx` | Badge for `supported` / `insufficient_evidence` / `contradicted` / `no_evidence` / `no_answer` |
| `AuditPanel.tsx` | Low-level audit view (stage latencies, signal scores) |
| `Header.tsx` / `Sidebar.tsx` | Application shell / navigation |

(Component names above reflect the `ui/src/components/` inventory; where a page composes a
sub-variant it is co-located in the same file.)

---

## 4.5 Hooks (6 hooks)

Custom hooks under `ui/src/hooks/`:

| Hook | Responsibility |
|------|----------------|
| `useQuery.ts` | `useMutation` for `POST /api/v1/query`; exposes answer/evidence/loading/error |
| `useExplain.ts` | `useMutation` for `POST /api/v1/explain` (no-LLM explainability) |
| `useProvenance.ts` | `useQuery` for `GET /api/v1/provenance/{id}` |
| `useRecentQuestions.ts` | Persists the recent-question history in `localStorage` |
| `useSettings.ts` | API base URL, theme, and display preferences (persisted) |
| `useTheme.ts` | Dark/light mode state and DOM class toggling |

All server-state hooks wrap TanStack React Query so caching, retries, and loading/error
states are handled uniformly.

---

## 4.6 API layer

`ui/src/api/client.ts`:

- Creates a single **axios** instance whose `baseURL` is `settings.apiBaseUrl` (default
  `/api/v1`, overridable in Settings; the Vite dev server proxies `/api` to the backend).
- Adds response interceptors for error normalisation and request timeouts.
- Exports typed functions: `queryQuestion()`, `explain()`, `getProvenance(id)`,
  `uploadDocument(file)`, and health checks.
- Types are declared in `ui/src/types/index.ts` and mirror the backend Pydantic schemas
  (`QueryResponse`, `EvidenceItem`, `ReasoningStep`, `VerificationResult`, `ProvenanceRecord`,
  etc.).

---

## 4.7 State management approach

- **Server state** → TanStack React Query (queries + mutations). Nothing about retrieval or
  provenance is stored in Redux-style global state.
- **Local UI state** → React hooks (`useState`/`useReducer`) within pages/components.
- **Persistent user preferences** → `localStorage` via `useSettings` / `useTheme`.
- **Recent questions** → `localStorage` via `useRecentQuestions`.

This split keeps the app simple: the backend is the source of truth; the client only caches.

---

## 4.8 Dev server and build

`ui/vite.config.ts`:

- React plugin (`@vitejs/plugin-react`).
- **Dev proxy**: `'/api'` → `http://localhost:8000` so the SPA talks to the FastAPI backend
  without CORS configuration during development.
- **Vitest** configuration (jsdom environment, setup file) for component/util tests.
- Production build outputs static assets to `ui/dist/`, served by `deploy/nginx/` in
  containers and by the SPA nginx config (`nginx-frontend.conf`).

Scripts (in `ui/package.json`): `dev`, `build`, `preview`, `lint`, `test`.

---

## 4.9 Utilities

`ui/src/utils/`:

- `format.ts` — number/date/score formatting, badge colour mapping.
- `graph.ts` — transforms the backend sub-graph payload into Cytoscape elements
  (nodes/edges, layout).
- `highlight.ts` — safe highlighting of query terms inside evidence snippets.
- Unit tests: `format.test.ts`, `graph.test.ts`, `highlight.test.ts`.

---

## 4.10 Frontend → backend contract

```text
Home ──► example queries ──► navigate(/explain)
Explain ──► useQuery ──► POST /api/v1/query
     ├─ AnswerCard (answer + citations + badge)
     ├─ EvidencePanel / EvidenceCard (evidence + scores)
     ├─ ReasoningChain
     ├─ KnowledgeGraph (sub-graph)
     ├─ HierarchyTree (active hierarchy path)
     ├─ ConfidenceGauge (composite confidence)
     └─ ProvenancePanel ──► GET /api/v1/provenance/{id}
Upload ──► uploadDocument ──► POST /api/v1/documents/upload ──► indexing summary
Settings ──► useSettings (API base URL, theme)
```

---

## 4.11 Accessibility and UX

- Semantic HTML with labelled inputs and keyboard-navigable graph/tree views.
- Tailwind utility classes with a consistent dark/light palette.
- Loading skeletons and error states surfaced by React Query; framer-motion transitions for
  answer/evidence reveal.
- Responsive layout (sidebar collapses on narrow viewports).

---

## 4.12 Key frontend files quick reference

| File | Responsibility |
|------|----------------|
| `ui/src/main.tsx` | React root |
| `ui/src/App.tsx` | Providers, router, shell |
| `ui/src/api/client.ts` | Axios instance + API functions |
| `ui/src/types/index.ts` | Shared interfaces |
| `ui/src/pages/Home.tsx` | Landing/example queries |
| `ui/src/pages/Explain.tsx` | QA workspace |
| `ui/src/pages/Upload.tsx` | Document upload |
| `ui/src/pages/Provenance.tsx` | Provenance browser |
| `ui/src/pages/Settings.tsx` | Settings |
| `ui/src/components/KnowledgeGraph.tsx` | Cytoscape KG view |
| `ui/src/components/HierarchyTree.tsx` | React Flow hierarchy view |
| `ui/src/components/ConfidenceGauge.tsx` | Recharts confidence gauge |
| `ui/vite.config.ts` | Dev proxy + Vitest config |
