import importlib.util
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = (
    ROOT / "paper" / "latex" / "scripts" / "generate_v05_answerability_assets.py"
)
GENERATOR_SPEC = importlib.util.spec_from_file_location(
    "v05_paper_asset_generator", GENERATOR_PATH
)
assert GENERATOR_SPEC is not None and GENERATOR_SPEC.loader is not None
generator = importlib.util.module_from_spec(GENERATOR_SPEC)
GENERATOR_SPEC.loader.exec_module(generator)

LEDGER_PATH = ROOT / "paper" / "latex" / "scripts" / "verify_v05_claim_ledger.py"
LEDGER_SPEC = importlib.util.spec_from_file_location(
    "v05_paper_claim_ledger", LEDGER_PATH
)
assert LEDGER_SPEC is not None and LEDGER_SPEC.loader is not None
ledger = importlib.util.module_from_spec(LEDGER_SPEC)
LEDGER_SPEC.loader.exec_module(ledger)


class V05PaperClaimValidationTests(unittest.TestCase):
    def test_single_row_rejects_ambiguous_metric_selection(self) -> None:
        frame = pd.DataFrame(
            [
                {"split": "evaluation", "policy": "target_only_forced"},
                {"split": "evaluation", "policy": "target_only_forced"},
            ]
        )

        with self.assertRaisesRegex(ValueError, "exactly one"):
            generator._single_row(
                frame,
                "target-only forced policy",
                split="evaluation",
                policy="target_only_forced",
            )

    def test_claim_value_validation_detects_a_changed_number(self) -> None:
        rows = [
            {
                "claim_id": "V05-01",
                "claim_text": "The evaluation contains 359 components.",
            }
        ]
        value_manifest = {
            "schema_version": 1,
            "protocol_id": "v0.5-answerability-frontier",
            "claims": {
                claim_id: {"expected_ledger_fragments": []}
                for claim_id in ledger.REQUIRED_CLAIM_IDS
            },
        }
        value_manifest["claims"]["V05-01"]["expected_ledger_fragments"] = ["360"]

        violations = ledger.check_recomputed_values(rows, value_manifest)

        self.assertEqual(1, len(violations))
        self.assertEqual(
            "claim_text_missing_recomputed_fragment", violations[0]["issue"]
        )

    def test_schema_rejects_missing_required_v05_claims(self) -> None:
        rows = [{"claim_id": "V05-01", "verification_status": ledger.VERIFIED_STATUS}]

        violations = ledger.check_schema(rows, ledger.REQUIRED_COLUMNS)

        self.assertTrue(
            any(item["issue"] == "required_claim_ids_mismatch" for item in violations)
        )

    def test_assertion_must_appear_in_declared_manuscript_file(self) -> None:
        rows = [
            {
                "claim_id": "V05-01",
                "manuscript_section": "Experiments",
                "manuscript_file": "sections/experiments.tex",
                "manuscript_assertion": r"\section*{Abstract}",
            }
        ]
        macro_source = (
            ROOT / "paper" / "latex" / "generated" / "v05_answerability_macros.tex"
        ).read_text(encoding="utf-8")

        violations = ledger.check_manuscript_locations_and_assertions(
            rows, macro_source
        )

        self.assertTrue(
            any(item["issue"] == "manuscript_assertion_missing" for item in violations)
        )

    def test_assertion_rejects_undefined_receipt_macro(self) -> None:
        rows = [
            {
                "claim_id": "V05-01",
                "manuscript_section": "Experiments",
                "manuscript_file": "sections/experiments.tex",
                "manuscript_assertion": r"\VFiveNoSuchMetric{}",
            }
        ]

        violations = ledger.check_manuscript_locations_and_assertions(rows, "")

        self.assertTrue(
            any(
                item["issue"] == "manuscript_assertion_uses_undefined_macro"
                for item in violations
            )
        )

    def test_assertion_can_bind_prose_and_generated_table(self) -> None:
        rows = [
            {
                "claim_id": "V05-03",
                "manuscript_section": "Results RQ1",
                "manuscript_file": (
                    "sections/results.tex||"
                    "generated/tables/table_v05_failure_accounting.tex"
                ),
                "manuscript_assertion": (
                    r"comparative forced policy also answered every arm but had "
                    r"\VFiveComparativeForcedRiskPercent{} observed error.||"
                    r"Comparative-forced errors & 126,764 & among 460,800 "
                    r"forced scope arms \\"
                ),
            }
        ]
        macro_source = (
            ROOT / "paper" / "latex" / "generated" / "v05_answerability_macros.tex"
        ).read_text(encoding="utf-8")

        violations = ledger.check_manuscript_locations_and_assertions(
            rows, macro_source
        )

        self.assertEqual([], violations)

    def test_report_display_formats_probabilities_and_zero_errors(self) -> None:
        self.assertEqual(r"39.1\%", generator._format_percent(0.3906119792))
        self.assertEqual(r"19.5\%", generator._format_percent(0.195208))
        self.assertEqual(
            "0 observed errors", generator._format_observed_error(0.0)
        )

    def test_presentation_figure_labels_use_reader_facing_percentages(self) -> None:
        self.assertEqual("39.1%", generator._plain_percent(0.3906119792))
        self.assertEqual("0%", generator._plain_percent(0.0))
        self.assertEqual("0 observed errors", generator._plain_observed_error(0.0))
        self.assertEqual("0.18", generator._compact_decimal(0.18))

    def test_generated_macro_validation_detects_frozen_value_mismatch(self) -> None:
        violations = ledger.check_generated_macros(
            r"\newcommand{\VFiveTargetForcedRisk}{0.400000}",
            {"VFiveTargetForcedRisk": "0.500000"},
        )

        self.assertEqual(1, len(violations))
        self.assertEqual(
            "generated_v05_macro_disagrees_with_frozen_evidence",
            violations[0]["issue"],
        )

    def test_generated_table_assertion_rejects_unbound_value(self) -> None:
        rows = [
            {
                "claim_id": "V05-03",
                "manuscript_file": "generated/tables/table_v05_failure_accounting.tex",
                "manuscript_assertion": "Comparative-forced errors & 126,765",
            }
        ]

        violations = ledger.check_generated_table_assertion_values(
            rows,
            {"VFiveComparativeForcedErrors": "126,764"},
            {"V05-03": ["126,764"]},
            {"20"},
        )

        self.assertEqual(1, len(violations))
        self.assertEqual(
            "generated_table_assertion_uses_unbound_number", violations[0]["issue"]
        )

    def test_generated_table_assertion_allows_frozen_protocol_labels(self) -> None:
        rows = [
            {
                "claim_id": "V05-11",
                "manuscript_file": "generated/tables/table_v05_certificate.tex",
                "manuscript_assertion": r"$q=25\%$ & 10.9\%",
            }
        ]

        violations = ledger.check_generated_table_assertion_values(
            rows,
            {},
            {"V05-11": ["0.109375"]},
            {"25"},
        )

        self.assertEqual([], violations)

    def test_receipt_bound_labels_include_protocol_percentages(self) -> None:
        _, _, labels = ledger.receipt_bound_display_values()

        self.assertTrue(
            {"0", "1", "5", "10", "20", "25", "50", "75", "100"}.issubset(
                labels
            )
        )
