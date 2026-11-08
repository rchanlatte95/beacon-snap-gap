// Readability check for the planner map mock-up (plain-language task T9).
//
// Usage (from the repo root, with the dev server running):
//   node docs/mockups/planner-map/check-readability.mjs http://localhost:5173/docs/mockups/planner-map/
//
// It loads the page in Chromium (Playwright) and collects the visible text OUTSIDE every
// `.how-we-know` element (the detail level may be technical) in these regions:
//   - the sidebar, once with "Compare with" set to Nothing and once for each other option
//   - the tract card for one No gap flagged tract (found by clicking the map)
//   - the tract card for one Classic Food Desert tract (first row of the high-need list),
//     also once for each "Compare with" option, because a layer can add card lines
//   - the tract card for each Insufficient data tract (links in the sidebar detail level)
// For each region it prints the Flesch-Kincaid grade level and the 5 hardest sentences.
// Exit code: 1 when a region is above grade 8; else 2 when the page or a region could not be
// loaded; else 0 (every region is at grade 8 or lower).
//
// Flesch-Kincaid grade level (Kincaid et al., 1975):
//   grade = 0.39 * (words / sentences) + 11.8 * (syllables / words) - 15.59
//
// Counting rules (written here, no extra dependency):
//   - Sentences: each line of rendered text (headings, labels, list rows, legend lines) is split
//     after ".", "!" or "?" followed by a space. Each non-empty piece is one sentence.
//   - Words: tokens with at least one letter or digit. "·", "/" and dashes between spaces are not words.
//   - Syllables: a common vowel-group heuristic. Lowercase, drop a silent final "e", "es" or "ed",
//     but keep a final consonant + "le" (table), then count groups of one or two vowels
//     (a, e, i, o, u, y); at least 1 per word. Words of 3 letters or fewer are 1 syllable.
//     Hyphenated words add their parts.
//   - Text is read with CSS text-transform turned off, so an upper-case heading is not read as
//     an acronym. Closed <details> other than .how-we-know are opened first, so that hidden
//     explore-level text is measured too.
//   - The "hardest sentences" list ranks sentences of 3 or more words. Shorter labels still
//     count in the region grade.
//   - All-capital acronyms (USDA, CDC) are read letter by letter: 1 syllable per letter, except
//     acronyms that are read as words (SNAP, FEMA, LILA).
//   - Numbers: a one-digit number is 1 syllable; a longer number (1,344 or 17.025%) is 3 syllables.
//     This is a cautious middle value: it raises the grade a little for text with many numbers.
import { chromium } from 'playwright'

const MAX_GRADE = 8
const url = process.argv[2]
if (!url) {
  console.error('Usage: node check-readability.mjs <dev server URL of the planner map page>')
  process.exit(2)
}

const SPOKEN_ACRONYMS = new Set(['SNAP', 'FEMA', 'LILA', 'NASA'])

function wordSyllables(raw) {
  const token = raw.replace(/^[^A-Za-z0-9]+|[^A-Za-z0-9%]+$/g, '')
  if (!token) return 0
  if (/\d/.test(token)) return token.replace(/\D/g, '').length <= 1 ? 1 : 3
  if (token.includes('-'))
    return token
      .split('-')
      .filter(Boolean)
      .reduce((sum, part) => sum + wordSyllables(part), 0)
  const letters = token.replace(/[^A-Za-z]/g, '')
  if (letters.length >= 2 && letters === letters.toUpperCase())
    return SPOKEN_ACRONYMS.has(letters) ? Math.max(1, (letters.match(/[AEIOUY]+/g) ?? []).length) : letters.length
  let w = letters.toLowerCase()
  if (w.length <= 3) return 1
  // A final consonant + "le" is spoken (ta-ble); other silent endings are dropped (make, homes).
  if (!/[^aeiouy]le$/.test(w)) w = w.replace(/(?:[^laeiouy]es|[^laeiouy]ed|[^aeiouy]e)$/, '')
  w = w.replace(/^y/, '')
  const groups = w.match(/[aeiouy]{1,2}/g)
  return Math.max(1, groups ? groups.length : 0)
}

const wordsOf = (sentence) => sentence.split(/[\s/·]+/).filter((t) => /[A-Za-z0-9]/.test(t))

function sentencesOf(text) {
  return text
    .split(/\n+/)
    .flatMap((line) => line.split(/(?<=[.!?])\s+/))
    .map((s) => s.replace(/\s+/g, ' ').trim())
    .filter((s) => wordsOf(s).length > 0)
}

function fk(sentences) {
  let words = 0
  let syll = 0
  for (const s of sentences)
    for (const w of wordsOf(s)) {
      words++
      syll += wordSyllables(w)
    }
  if (words === 0 || sentences.length === 0) return { words, syll, grade: 0 }
  return { words, syll, grade: 0.39 * (words / sentences.length) + 11.8 * (syll / words) - 15.59 }
}

// Visible text of a region, without any `.how-we-know` element. A <select> counts only its
// chosen option, because that is what a person sees.
async function regionText(page, selector) {
  return page.evaluate((sel) => {
    const el = document.querySelector(sel)
    if (!el) return null
    const undo = []
    const style = document.createElement('style')
    style.textContent = '* { text-transform: none !important; }'
    document.head.append(style)
    undo.push(() => style.remove())
    for (const d of el.querySelectorAll('details:not(.how-we-know):not([open])')) {
      d.open = true
      undo.push(() => (d.open = false))
    }
    for (const h of el.querySelectorAll('.how-we-know')) {
      const prev = h.style.display
      h.style.display = 'none'
      undo.push(() => (h.style.display = prev))
    }
    for (const s of el.querySelectorAll('select')) {
      const span = document.createElement('span')
      span.textContent = s.selectedOptions[0]?.textContent ?? ''
      const prev = s.style.display
      s.style.display = 'none'
      s.after(span)
      undo.push(() => {
        span.remove()
        s.style.display = prev
      })
    }
    const text = el.innerText
    for (const u of undo.reverse()) u()
    return text
  }, selector)
}

const results = []
let setupError = false

async function measure(page, name, selector) {
  const text = await regionText(page, selector)
  if (text === null) {
    console.error(`ERROR: region "${name}" not found (${selector}).`)
    setupError = true
    return
  }
  const sentences = sentencesOf(text)
  const all = fk(sentences)
  const hardest = sentences
    .filter((s) => wordsOf(s).length >= 3)
    .map((s) => ({ s, ...fk([s]) }))
    .sort((a, b) => b.grade - a.grade)
    .slice(0, 5)
  results.push({ name, ...all, sentences: sentences.length, hardest })
}

const cardClass = (page) =>
  page.evaluate(() => document.querySelector('.card .class-badge')?.textContent?.trim() ?? null)

async function closeCard(page) {
  if (await page.$('.card .close')) await page.click('.card .close')
  await page.waitForTimeout(300)
}

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
const consoleErrors = []
page.on('console', (m) => m.type() === 'error' && consoleErrors.push(m.text()))
page.on('pageerror', (e) => consoleErrors.push(String(e)))

try {
  await page.goto(url, { waitUntil: 'load', timeout: 60000 })
  await page.waitForSelector('.maplibregl-canvas', { timeout: 20000 })
  await page.waitForSelector('.sidebar', { timeout: 20000 })
  await page.waitForTimeout(2000)

  // Sidebar, once per "Compare with" option.
  const compare = 'select[aria-label="Compare with"]'
  const options = await page.$$eval(`${compare} option`, (os) =>
    os.map((o) => ({ value: o.value, label: o.textContent ?? '' })),
  )
  await measure(page, 'Sidebar (Compare with: Nothing)', '.sidebar')
  const compareOptions = options.filter((o) => o.value !== '')
  for (const o of compareOptions) {
    await page.selectOption(compare, o.value)
    await page.waitForTimeout(500)
    await measure(page, `Sidebar (Compare with: ${o.label})`, '.sidebar')
  }
  if (compareOptions.length) await page.selectOption(compare, '')
  if (compareOptions.length === 0) console.log('Note: the "Compare with" select has no options yet.\n')

  // No gap flagged card: click points on the map until a No gap flagged tract opens.
  const box = await page.locator('.map-col').boundingBox()
  let nogapFound = false
  if (box) {
    search: for (let row = 1; row <= 6; row++)
      for (let col = 1; col <= 8; col++) {
        const x = box.x + ((box.width - 420) * col) / 9
        const y = box.y + (box.height * row) / 7
        await page.mouse.click(x, y)
        await page.waitForTimeout(400)
        const cls = await cardClass(page)
        if (cls?.startsWith('No gap flagged')) {
          await measure(page, `No gap flagged card (${await page.textContent('.card h3')})`, '.card')
          nogapFound = true
          break search
        }
        if (cls) await closeCard(page)
      }
  }
  if (!nogapFound) {
    console.error('ERROR: no No gap flagged tract card could be opened from the map.')
    setupError = true
  }
  await closeCard(page)

  // Classic Food Desert card: the first row of the high-need list.
  await page.click('.tract-list button >> nth=0')
  await page.waitForSelector('.card')
  await page.waitForTimeout(800)
  if ((await cardClass(page))?.startsWith('Classic Food Desert')) {
    const name = await page.textContent('.card h3')
    await measure(page, `Classic Food Desert card (${name})`, '.card')
    for (const o of compareOptions) {
      await page.selectOption(compare, o.value)
      await page.waitForTimeout(500)
      await measure(page, `Classic Food Desert card (${name}, Compare with: ${o.label})`, '.card')
    }
    if (compareOptions.length) await page.selectOption(compare, '')
  } else {
    console.error('ERROR: the first high-need list row did not open a Classic Food Desert card.')
    setupError = true
  }
  await closeCard(page)

  // Insufficient data cards: the tract links in the sidebar detail level.
  await page.click('.sidebar .how-we-know > summary')
  const links = page.locator('.sidebar .how-we-know button.linklike')
  let insufficientFound = 0
  for (let i = 0; i < (await links.count()); i++) {
    await links.nth(i).click()
    await page.waitForTimeout(800)
    if ((await cardClass(page))?.startsWith('Insufficient data')) {
      await measure(page, `Insufficient data card (${await page.textContent('.card h3')})`, '.card')
      insufficientFound++
    }
    await closeCard(page)
  }
  if (insufficientFound === 0) {
    console.error('ERROR: no Insufficient data tract card could be opened.')
    setupError = true
  }
} catch (e) {
  console.error(`ERROR: ${e instanceof Error ? e.message : String(e)}`)
  setupError = true
} finally {
  await browser.close()
}

let tooHard = 0
for (const r of results) {
  const pass = r.grade <= MAX_GRADE
  if (!pass) tooHard++
  console.log(`${pass ? 'PASS' : 'FAIL'}  grade ${r.grade.toFixed(1)}  ${r.name}`)
  console.log(`      ${r.words} words, ${r.sentences} sentences, ${r.syll} syllables`)
  console.log('      Hardest sentences:')
  for (const h of r.hardest) console.log(`        ${h.grade.toFixed(1).padStart(5)}  ${h.s}`)
  console.log('')
}
if (consoleErrors.length) console.log(`Console errors on the page: ${JSON.stringify(consoleErrors)}`)
else console.log('Console errors on the page: none')
console.log(`Regions: ${results.length}, above grade ${MAX_GRADE}: ${tooHard}`)
process.exit(tooHard > 0 ? 1 : setupError ? 2 : 0)
