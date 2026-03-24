ALTER TABLE subscription_tiers
ADD COLUMN has_addon_access INTEGER NOT NULL DEFAULT 0;

UPDATE subscription_tiers
SET has_addon_access = CASE
  WHEN tier = 1 THEN 0
  ELSE 1
END
WHERE has_addon_access IS NULL OR has_addon_access = 0;
