pub(super) const RUNS: &str = "WITH summaries AS (
    SELECT id, label, created_at, target_name,
           share_hash IS NOT NULL AS shared,
           CASE
               WHEN result_unit <> 'result' THEN result_count
               WHEN jsonb_typeof(result -> 'sets') = 'array' THEN jsonb_array_length(result -> 'sets')
               WHEN jsonb_typeof(result -> 'pairs') = 'array' THEN jsonb_array_length(result -> 'pairs')
               WHEN jsonb_typeof(result -> 'assays') = 'array' THEN jsonb_array_length(result -> 'assays')
               WHEN jsonb_typeof(result -> 'tiles') = 'array' THEN jsonb_array_length(result -> 'tiles')
               WHEN jsonb_typeof(result -> 'primers') = 'array' THEN jsonb_array_length(result -> 'primers')
               WHEN jsonb_typeof(result -> 'junctions') = 'array' THEN jsonb_array_length(result -> 'junctions')
               ELSE 0
           END AS result_count,
           CASE
               WHEN result_unit <> 'result' THEN result_unit
               WHEN jsonb_typeof(result -> 'sets') = 'array' THEN 'set'
               WHEN jsonb_typeof(result -> 'pairs') = 'array' THEN 'pair'
               WHEN jsonb_typeof(result -> 'assays') = 'array' THEN 'assay'
               WHEN jsonb_typeof(result -> 'tiles') = 'array' THEN 'tile'
               WHEN jsonb_typeof(result -> 'primers') = 'array' THEN 'primer'
               WHEN jsonb_typeof(result -> 'junctions') = 'array' THEN 'junction'
               ELSE 'result'
           END AS result_unit
    FROM runs
    WHERE project_id = $1
)
SELECT id, label, created_at,
       CASE WHEN result_unit = 'pair' THEN result_count ELSE 0 END AS pair_count,
       result_count,
       result_unit,
       target_name,
       shared
FROM summaries
ORDER BY created_at DESC";
