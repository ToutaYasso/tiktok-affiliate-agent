# n8n Workflows

| Fichier | Description | Status |
|---------|-------------|--------|
| 01-product-discovery.json | Produits trending Amazon/AliExpress · scoring Gemini | ✅ Fonctionnel |
| 02-script-generation.json | Script vidéo via Gemini API | 🟡 En cours |
| 03-audio-generation.json | Voix off ElevenLabs | 🔴 À créer |
| 04-video-assembly.json | Assemblage FFmpeg | 🔴 À créer |
| 05-tiktok-publish.json | Publication TikTok | 🔴 À créer |
| 06-metrics-analysis.json | Analyse + optimisation IA | 🔴 À créer |

## Workflow 01 — Product Discovery ✅

**Nœuds :**
1. `Schedule 6h` — déclencheur toutes les 6h
2. `Products List` — liste de produits affiliés (Code node, mock → à remplacer par API Amazon/AliExpress)
3. `Gemini AI Scoring` — sélection top 3 via `gemini-3.1-flash-lite` · clé via `$env.GEMINI_API_KEY`
4. `Parse Claude Response` — extraction JSON Gemini (`candidates[0].content.parts[0].text`) + split en 3 items
5. `Save to PostgreSQL` — insertion en base (platform, title, price, commission_rate, category, score, affiliate_link, why_viral, hook)
6. `Output → Workflow 02` — transmission des 3 produits au workflow suivant

**Modèle IA :** `gemini-3.1-flash-lite` · retry x4 · wait 7s

## Workflow 02 — Script Generation 🟡

**Nœuds :**
1. `Trigger from WF01` — réception des 3 produits via Execute Workflow
2. `Gemini Script Generator` — génération script TikTok (hook 3s, démo 15s, CTA 7s) par produit
3. `Parse Script` — extraction titre + scènes + CTA du JSON Gemini
4. `Save Script to DB` — mise à jour de la table `videos` avec le script
5. `Output → Workflow 03` — transmission à la génération audio

**Modèle IA :** `gemini-3.1-flash-lite`
