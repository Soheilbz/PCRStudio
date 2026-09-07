#[cfg(test)]
mod sequence_asset_projection_tests {
    use super::super::{
        collect_sequence_candidates, nucleotide_document_alphabet, pointer_for, DocumentPathPart,
        SequenceCandidate,
    };

    #[test]
    fn only_large_nucleotide_documents_cross_the_asset_boundary() {
        let sequence = "ACGT".repeat(pcr_contracts::MAX_SEQUENCE_ASSET_EXTERNALIZE_BYTES / 4);
        assert_eq!(nucleotide_document_alphabet(&sequence), Some("dna"));
        assert_eq!(nucleotide_document_alphabet("ACGTACGT"), None);

        let prose = "scientific report ".repeat(5000);
        assert_eq!(nucleotide_document_alphabet(&prose), None);
    }

    #[test]
    fn fasta_is_detected_without_treating_headers_as_sequence_bases() {
        let bases = "AUGC".repeat(pcr_contracts::MAX_SEQUENCE_ASSET_EXTERNALIZE_BYTES / 4);
        let fasta = format!(">target one\n{bases}\n");
        assert_eq!(
            nucleotide_document_alphabet(&fasta),
            Some("nucleotide-fasta")
        );
    }

    #[test]
    fn document_paths_are_stable_rfc6901_style_addresses() {
        let path = vec![
            DocumentPathPart::Key("targets".to_owned()),
            DocumentPathPart::Index(2),
            DocumentPathPart::Key("a/b~c".to_owned()),
        ];
        assert_eq!(pointer_for(&path), "/targets/2/a~1b~0c");
    }

    #[test]
    fn nested_sequence_candidates_keep_distinct_field_paths() {
        let sequence = "ACGT".repeat(pcr_contracts::MAX_SEQUENCE_ASSET_EXTERNALIZE_BYTES / 4);
        let value = serde_json::json!({
            "template": sequence,
            "targets": [{"background": "TGCA".repeat(pcr_contracts::MAX_SEQUENCE_ASSET_EXTERNALIZE_BYTES / 4)}]
        });
        let mut candidates: Vec<SequenceCandidate> = Vec::new();
        collect_sequence_candidates(&value, &mut Vec::new(), &mut candidates);
        let mut paths: Vec<_> = candidates.into_iter().map(|item| item.field_path).collect();
        paths.sort();
        assert_eq!(paths, vec!["/targets/0/background", "/template"]);
    }
}

#[cfg(test)]
mod configuration_tests {
    use super::super::normalize_database_url_secret;

    #[test]
    fn database_secret_has_one_outer_whitespace_policy() {
        assert_eq!(
            normalize_database_url_secret(Some(
                "  postgres://pcr:secret@db/pcrstudio\r\n".to_owned()
            ))
            .as_deref(),
            Some("postgres://pcr:secret@db/pcrstudio")
        );
        assert_eq!(
            normalize_database_url_secret(Some(" \t\r\n".to_owned())),
            None
        );
        assert_eq!(normalize_database_url_secret(None), None);
    }
}
