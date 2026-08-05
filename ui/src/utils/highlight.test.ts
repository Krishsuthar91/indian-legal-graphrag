import { countMatches, splitMatches } from './highlight'

describe('splitMatches', () => {
  it('returns a single unmatched part when no keywords', () => {
    expect(splitMatches('plain text', [])).toEqual([{ text: 'plain text', matched: false }])
  })

  it('marks keyword occurrences case-insensitively', () => {
    const parts = splitMatches('Murder is punished under Section 302', ['murder'])
    expect(parts.filter((p) => p.matched).map((p) => p.text)).toEqual(['Murder'])
  })

  it('matches longest keyword first', () => {
    const parts = splitMatches('prison for life sentence', ['prison', 'prison for life'])
    expect(parts.filter((p) => p.matched).map((p) => p.text)).toEqual(['prison for life'])
  })

  it('preserves unmatched fragments', () => {
    const parts = splitMatches('a long boring statement here', ['boring'])
    const texts = parts.map((p) => p.text).join('|')
    expect(texts).toContain('a long ')
    expect(texts).toContain(' statement here')
  })

  it('ignores single-character keywords', () => {
    expect(splitMatches('a b c', ['a', 'b'])).toEqual([{ text: 'a b c', matched: false }])
  })
})

describe('countMatches', () => {
  it('counts matched segments', () => {
    const parts = splitMatches('x murder y murder z', ['murder'])
    expect(countMatches(parts)).toBe(2)
  })
})
