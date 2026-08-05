import { splitMatches } from '../utils/highlight'

interface HighlightTextProps {
  text: string
  keywords: string[]
  className?: string
}

export default function HighlightText({ text, keywords, className }: HighlightTextProps) {
  const parts = splitMatches(text, keywords)
  return (
    <span className={className}>
      {parts.map((part, i) =>
        part.matched ? (
          <mark
            key={`${i}-${part.text}`}
            className="rounded-sm bg-yellow-200 px-0.5 text-inherit dark:bg-yellow-500/30"
          >
            {part.text}
          </mark>
        ) : (
          <span key={`${i}-${part.text}`}>{part.text}</span>
        ),
      )}
    </span>
  )
}
