import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Suspense, lazy } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import Header from './components/Header'
import LoadingOverlay from './components/LoadingOverlay'
import { useDarkMode } from './hooks/useDarkMode'

const Home = lazy(() => import('./pages/Home'))
const Explain = lazy(() => import('./pages/Explain'))
const Upload = lazy(() => import('./pages/Upload'))
const Provenance = lazy(() => import('./pages/Provenance'))
const Settings = lazy(() => import('./pages/Settings'))

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
})

export default function App() {
  const [dark, setDark] = useDarkMode()
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900 antialiased dark:bg-slate-950 dark:text-slate-100">
          <Header dark={dark} onToggleDark={setDark} />
          <main className="flex-1">
            <Suspense fallback={<LoadingOverlay label="Loading page…" />}>
              <Routes>
                <Route path="/" element={<Home />} />
                <Route path="/explain" element={<Explain />} />
                <Route path="/upload" element={<Upload />} />
                <Route path="/provenance" element={<Provenance />} />
                <Route path="/provenance/:id" element={<Provenance />} />
                <Route path="/settings" element={<Settings dark={dark} onToggleDark={setDark} />} />
                <Route path="*" element={<Home />} />
              </Routes>
            </Suspense>
          </main>
          <footer className="border-t border-slate-200 py-4 text-center text-[11px] text-slate-400 dark:border-slate-800 dark:text-slate-500">
            Module 8 · Explainable Multilingual Hierarchical Graph-RAG · HHGR
          </footer>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
