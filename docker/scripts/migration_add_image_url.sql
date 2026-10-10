-- Migration WF04: ajouter image_url à la table products
-- À exécuter une seule fois sur la DB affiliate_agent

ALTER TABLE products ADD COLUMN IF NOT EXISTS image_url TEXT;

-- Vérification
SELECT column_name, data_type FROM information_schema.columns
WHERE table_name = 'products' AND column_name = 'image_url';
