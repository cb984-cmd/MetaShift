"""Validation helpers for pre-outcome Method Code transition taxonomy."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


TRANSITION_KEY_COLUMNS = (
    "old_method_code",
    "old_method_name",
    "new_method_code",
    "new_method_name",
)
REQUIRED_COLUMNS = (
    *TRANSITION_KEY_COLUMNS,
    "old_analyzer_family",
    "new_analyzer_family",
    "transition_class",
    "nda_related",
    "same_hardware_family",
    "classification_basis",
    "official_source",
    "review_status",
)
VALID_TRANSITION_CLASSES = frozenset(
    {
        "administrative_data_processing",
        "same_analyzer_configuration",
        "cross_analyzer_family",
        "unresolved",
    }
)
BOOLEAN_VALUES = frozenset({"true", "false"})


def observed_transition_pairs(anchors: pd.DataFrame) -> pd.DataFrame:
    """Extract unique metadata-only transition pairs from the anchor inventory."""

    source_columns = (
        "previous_method_code",
        "previous_method_name",
        "method_code",
        "method_name",
    )
    missing = set(source_columns).difference(anchors.columns)
    if missing:
        raise ValueError(f"Anchor inventory lacks columns: {sorted(missing)}")
    pairs = anchors.loc[:, source_columns].rename(
        columns={
            "previous_method_code": "old_method_code",
            "previous_method_name": "old_method_name",
            "method_code": "new_method_code",
            "method_name": "new_method_name",
        }
    )
    return (
        pairs.astype("string")
        .drop_duplicates()
        .sort_values(list(TRANSITION_KEY_COLUMNS), kind="stable")
        .reset_index(drop=True)
    )


def validate_transition_taxonomy(
    taxonomy: pd.DataFrame, observed_pairs: pd.DataFrame
) -> pd.DataFrame:
    """Require one complete, metadata-matching taxonomy row for every pair."""

    missing = set(REQUIRED_COLUMNS).difference(taxonomy.columns)
    if missing:
        raise ValueError(f"Taxonomy lacks columns: {sorted(missing)}")
    normalized = taxonomy.loc[:, REQUIRED_COLUMNS].astype("string").fillna("")
    if normalized.duplicated(list(TRANSITION_KEY_COLUMNS)).any():
        raise ValueError("Taxonomy contains duplicate Method Code transition pairs.")
    empty_columns = [
        column
        for column in REQUIRED_COLUMNS
        if normalized[column].str.strip().eq("").any()
    ]
    if empty_columns:
        raise ValueError(f"Taxonomy has empty required fields: {empty_columns}")
    invalid_classes = set(normalized["transition_class"]).difference(
        VALID_TRANSITION_CLASSES
    )
    if invalid_classes:
        raise ValueError(
            f"Taxonomy has invalid transition classes: {sorted(invalid_classes)}"
        )
    for column in ("nda_related", "same_hardware_family"):
        invalid_values = set(normalized[column].str.lower()).difference(BOOLEAN_VALUES)
        if invalid_values:
            raise ValueError(
                f"Taxonomy column {column} must use true/false; found "
                f"{sorted(invalid_values)}"
            )
    observed = observed_pairs.loc[:, TRANSITION_KEY_COLUMNS].astype("string")
    observed_keys = set(
        tuple(row) for row in observed.itertuples(index=False, name=None)
    )
    taxonomy_keys = set(
        tuple(row)
        for row in normalized.loc[:, TRANSITION_KEY_COLUMNS].itertuples(
            index=False, name=None
        )
    )
    missing_pairs = observed_keys.difference(taxonomy_keys)
    extra_pairs = taxonomy_keys.difference(observed_keys)
    if missing_pairs or extra_pairs:
        raise ValueError(
            "Taxonomy must exactly cover observed metadata transition pairs; "
            f"missing={len(missing_pairs)}, extra={len(extra_pairs)}."
        )
    return normalized.sort_values(list(TRANSITION_KEY_COLUMNS), kind="stable").reset_index(
        drop=True
    )


def load_transition_taxonomy(
    path: Path, anchors: pd.DataFrame
) -> pd.DataFrame:
    """Load and validate the frozen taxonomy against metadata-only anchors."""

    taxonomy = pd.read_csv(path, dtype="string")
    return validate_transition_taxonomy(taxonomy, observed_transition_pairs(anchors))
