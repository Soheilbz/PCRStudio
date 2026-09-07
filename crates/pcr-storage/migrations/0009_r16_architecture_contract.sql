-- R16 architecture closure changes defaults for future documents only.
-- Historical project/run rows retain the contract/schema versions they were
-- originally written with; read migrations expose current views without
-- rewriting reproducibility evidence.
ALTER TABLE projects_all ALTER COLUMN module_contract_version SET DEFAULT '2.1.0';
ALTER TABLE runs ALTER COLUMN result_schema_version SET DEFAULT 4;
ALTER TABLE runs ALTER COLUMN module_contract_version SET DEFAULT '2.1.0';
