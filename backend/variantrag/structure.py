"""Structural context requires an explicit, sequence-verified transcript/UniProt mapping."""

import re


def structural_context(variant, mapping, http):
    if "missense_variant" not in variant["consequences"]:
        return {"status": "not_requested", "reason": "Not a missense candidate"}
    if mapping.get("transcript") != variant.get("transcript"):
        return {"status": "unavailable", "reason": "Transcript version does not match mapping"}
    if mapping.get("genome_build") != variant["genome_build"] or not mapping.get("source"):
        return {"status": "unavailable", "reason": "Mapping needs assembly and source provenance"}
    accession = mapping.get("uniprot_accession", "")
    if not re.fullmatch(r"[A-Z0-9]{6,10}(?:-\d+)?", accession):
        return {"status": "unavailable", "reason": "Missing valid UniProt accession"}
    try:
        entry = http.get(f"https://rest.uniprot.org/uniprotkb/{accession}.json")
        sequence = entry["sequence"]["value"]
        if mapping.get("protein_sequence") != sequence:
            return {"status": "unavailable", "reason": "Translated transcript and UniProt sequence mismatch"}
        position = mapping.get("residue_position")
        if (
            not isinstance(position, int)
            or not 1 <= position <= len(sequence)
            or sequence[position - 1] != mapping.get("reference_residue")
        ):
            return {"status": "unavailable", "reason": "Residue mapping not verified"}
        models = http.get(f"https://alphafold.ebi.ac.uk/api/prediction/{accession}")
        if not models:
            return {"status": "no_match", "reason": "No AlphaFold model"}
        return {
            "status": "available",
            "data": {
                "mapping": mapping,
                "uniprot_sequence_length": len(sequence),
                "models": models,
                "residue_plddt": None,
                "limitation": "Residue confidence not extracted; structural context does not contribute ranking points",
            },
        }
    except (KeyError, ValueError) as exc:
        return {"status": "error", "reason": str(exc)}
