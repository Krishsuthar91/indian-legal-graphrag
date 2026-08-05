import { motion } from 'framer-motion'

export default function LoadingOverlay({ label = 'Working…' }: { label?: string }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-4 bg-white/70 backdrop-blur-sm dark:bg-slate-950/70"
      role="status"
      aria-live="polite"
      aria-label={label}
    >
      <motion.div
        animate={{ rotate: 360 }}
        transition={{ repeat: Infinity, duration: 0.9, ease: 'linear' }}
        className="h-12 w-12 rounded-full border-4 border-slate-200 border-t-indigo-500 dark:border-slate-700 dark:border-t-indigo-400"
      />
      <p className="text-sm text-slate-600 dark:text-slate-300">{label}</p>
    </motion.div>
  )
}
