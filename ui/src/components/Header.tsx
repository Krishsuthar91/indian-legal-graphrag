import { NavLink } from 'react-router-dom'

interface HeaderProps {
  dark: boolean
  onToggleDark: (next: boolean) => void
}

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-lg px-3 py-1.5 text-sm font-medium transition ${
    isActive
      ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-500/20 dark:text-indigo-300'
      : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
  }`

export default function Header({ dark, onToggleDark }: HeaderProps) {
  return (
    <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/80 backdrop-blur dark:border-slate-800 dark:bg-slate-950/80">
      <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-3">
        <NavLink to="/" className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold text-white">
            ⚖
          </span>
          <span className="hidden text-sm font-semibold text-slate-800 sm:block dark:text-slate-100">
            Legal Graph-RAG
          </span>
        </NavLink>
        <nav className="ml-auto flex items-center gap-1">
          <NavLink to="/" className={linkClass} end>
            Home
          </NavLink>
          <NavLink to="/explain" className={linkClass}>
            Explain
          </NavLink>
          <NavLink to="/upload" className={linkClass}>
            Upload
          </NavLink>
          <NavLink to="/provenance" className={linkClass}>
            Provenance
          </NavLink>
          <NavLink to="/settings" className={linkClass}>
            Settings
          </NavLink>
          <button
            type="button"
            onClick={() => onToggleDark(!dark)}
            aria-label="Toggle dark mode"
            className="ml-2 rounded-lg border border-slate-200 px-2.5 py-1.5 text-sm text-slate-600 transition hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            {dark ? '☀' : '☾'}
          </button>
        </nav>
      </div>
    </header>
  )
}
