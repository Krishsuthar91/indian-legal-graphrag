export interface MatchPart {
  text: string
  matched: boolean
}

export function splitMatches(text: string, keywords: string[]): MatchPart[] {
  const haystack = text.toLowerCase()
  const keys = Array.from(
    new Set(
      keywords
        .map((k) => k.trim().toLowerCase())
        .filter((k) => k.length >= 2)
        .sort((a, b) => b.length - a.length),
    ),
  )
  if (keys.length === 0 || !text) return [{ text, matched: false }]

  let cursor = 0
  const parts: MatchPart[] = []

  while (cursor < text.length) {
    let bestIndex = -1
    let bestKey = ''
    for (const key of keys) {
      const idx = haystack.indexOf(key, cursor)
      if (idx !== -1 && (bestIndex === -1 || idx < bestIndex)) {
        bestIndex = idx
        bestKey = key
      }
    }
    if (bestIndex === -1) {
      parts.push({ text: text.slice(cursor), matched: false })
      break
    }
    if (bestIndex > cursor) {
      parts.push({ text: text.slice(cursor, bestIndex), matched: false })
    }
    parts.push({ text: text.slice(bestIndex, bestIndex + bestKey.length), matched: true })
    cursor = bestIndex + bestKey.length
  }

  return parts
}

export function countMatches(parts: MatchPart[]): number {
  return parts.filter((p) => p.matched).length
}
