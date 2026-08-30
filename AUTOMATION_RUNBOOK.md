# MetaShift autonomous execution runbook

This runbook governs each scheduled project pass. It prevents unattended work
from turning preliminary results into unsupported claims.

## Per-pass checklist

1. Read `PROJECT_PLAN.md`, open todos, Git status, and the latest result files.
2. Select the next incomplete task whose dependencies are satisfied.
3. Inspect the relevant inputs and preserve the frozen study protocol.
4. Implement one coherent unit of work; do not silently broaden the research
   question or alter the held-out evaluation set.
5. Run the smallest targeted test or experiment that validates the change.
6. Record artifacts, exclusions, failures, configuration, and provenance.
7. Update `PROJECT_PLAN.md` only when the task state or evidence changes.
8. Commit and push code, protocol, and non-sensitive documentation; never add
   raw data, API responses, generated experiment artifacts, or credentials.
9. Send an hourly status message covering completed work, current result,
   next task, and any blocker.

## Execution axis

| Phase | Objective | Completion evidence | Stop condition |
| --- | --- | --- | --- |
| B1 | Complete six-type comparative synthetic benchmark | Saved per-event results, CIs, and metric table | Label, leakage, or reproducibility defect |
| B2 | Freeze benchmark configuration | Versioned config and preregistration | Parameters chosen after configuration freeze |
| B3 | Audit real metadata anchors | Full result and exclusion inventories | Anchor treated as confirmed physical bias |
| V1 | Audit all real method transitions | Full result and exclusion inventories | Pre-fit failure dominates eligible events |
| V2 | Integrate QA and same-site POC evidence | Tiered external-validation table | Evidence is insufficient for causal wording |
| V3 | Run placebos, ablations, and sensitivity analyses | Saved comparison tables | Main claim is not robust |
| V4 | Run independent 88502 analysis | Separate pipeline and results | Parameter codes become mixed |
| D1 | Produce figures, report inputs, and reproducibility package | Re-run results from clean environment | Any result cannot be traced to code/config |

An evidence shortfall, data-integrity defect, or irreversible research decision
pauses the dependent phase and is reported immediately.
