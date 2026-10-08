# n8n Workflows

| Fichier | Description | Status |
|---------|-------------|--------|
| 01-product-discovery.json | Produits trending Amazon/AliExpress · scoring Gemini | 🟡 En cours (bug Parse node) |
| 02-script-generation.json | Script vidéo via Gemini API | 🔴 A créer |
| 03-audio-generation.json | Voix off ElevenLabs | 🔴 A créer |
| 04-video-assembly.json | Assemblage FFmpeg | 🔴 A créer |
| 05-tiktok-publish.json | Publication TikTok | 🔴 A créer |
| 06-metrics-analysis.json | Analyse + optimisation IA | 🔴 A créer |

## Workflow 01 — Product Discovery

**Nœuds :**
1. `Schedule 6h` — déclencheur toutes les 6h
2. `Products List` — fetch produits affiliés (HTTP Request)
3. `Gemini AI Scoring` — sélection top 3 via `gemini-3.1-flash-lite`
4. `Parse Gemini Response` — extraction JSON + split en 3 items ⚠️ bug à corriger
5. `Save to PostgreSQL` — insertion en base (bloqué par le bug)
6. `Output → Workflow 02` — transmission au workflow suivant (bloqué)

**Modèle IA :** `gemini-3.1-flash-lite` (clé via `$env.GEMINI_API_KEY`)

**Bug connu :** le nœud Parse utilise le chemin Claude/OpenAI (`choices[0]`)
au lieu du chemin Gemini (`candidates[0].content.parts[0].text`). À corriger.
