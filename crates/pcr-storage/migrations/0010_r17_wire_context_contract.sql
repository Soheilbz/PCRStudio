-- R17 separates browser semantic readiness from HTTP wire validation.
-- Existing historical rows keep their recorded contract version; only future writes
-- default to the new contract identity.
ALTER TABLE projects_all ALTER COLUMN module_contract_version SET DEFAULT '2.2.0';
ALTER TABLE runs ALTER COLUMN module_contract_version SET DEFAULT '2.2.0';
