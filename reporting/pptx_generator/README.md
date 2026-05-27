# PolarisBI PPTX Generator

Consulting-grade PowerPoint generator with 4 selectable identity systems.

## Identities

- **mckinsey** — Deep blue #051C2C, Georgia/Arial, editorial gravitas
- **bcg** — Forest green #147B58, framework-heavy, 2x2 matrix templates
- **bain** — Red #CB2026, 72pt stat heroes, heavy whitespace
- **polaris** — Dark #0C1C23 + Signal #1F78B4, young analyst signature (DEFAULT)

## Usage

```bash
# Install dependencies (first time only)
npm install

# Generate a sample deck
node generate.js --input samples/sample-bri-life.json --output out/test.pptx --identity polaris

# Or use npm scripts
npm run test:polaris
```

## Input JSON schema

See `samples/sample-bri-life.json` for the full structure. Minimum required fields:

```json
{
  "title": "BRI Life Industry Snapshot",
  "subtitle": "Q4 2024 Performance Review",
  "client": "BRI Life Internal",
  "author": "Lidharmawan Suryaatmadja",
  "date": "2026-05-28",
  "language": "en",
  "sections": [
    { "type": "cover" },
    { "type": "exec_summary", "data": {...} },
    { "type": "kpi_dashboard", "data": {...} }
  ]
}
```

## Architecture

- `identities.js` — Brand token registry (colors, fonts, sizes, margins, chart palettes)
- `masters.js` — Slide master factory (cover, content, section, appendix)
- `helpers/` — Reusable primitives (text, chart, icon, chip, layout)
- `slides/` — Slide-type builders (one per slide pattern)
- `generate.js` — CLI orchestrator

## License

Internal use only.
