# MMM Data Governance Guardrails

**Automated validation and hallucination detection for media mix modeling and LLM-assisted BI pipelines.**

---

## The Problem

As companies push LLM-generated analytics into production reporting, hallucinations don't fail loudly. A model returns numbers that look plausible, sit correctly in the schema, and violate the underlying business math. Those errors survive review because nothing about them looks wrong until someone recomputes them by hand.

Media mix modeling is especially exposed. The data is multi-year, multi-channel, and heavily aggregated, so a misallocated cohort or an impossible lift figure is invisible in a summary table.

### Patterns this framework catches

- **Budget violations** — spend allocated beyond the annual budget, or negative spend
- **Multi-year bucketization errors** — conversions growing 300% while spend grows 5%, or a year's data silently landing in the wrong cohort
- **Reach impossibilities** — reach exceeding the addressable universe; frequency below 1
- **Attribution logic failures** — weights outside 0–1, or attributed revenue exceeding total revenue
- **Incrementality hallucinations** — incremental conversions exceeding total conversions; ROAS implying a 20x return; test cells too small to support the claim

---

## The Solution

A Pydantic-based validation layer that sits between model output and the BI pipeline. Business constraints are encoded as schemas, so violations surface as validation failures instead of dashboard rows.

```python
from guardrails.schema_validator import DataContractValidator

validator = DataContractValidator()
result = validator.validate(data, 'multi_year_mmm', 'record_123')

if not result.passed:
    print(f"Validation failed: {result.errors}")
```

---

## What Gets Validated

**Budget and spend** (`MediaMixMetrics`)
Spend cannot be negative or exceed the annual budget. CPM is derived when not supplied.

**Reach and frequency** (`ReachAndFrequency`)
Reach cannot exceed the addressable universe. Frequency must be at least 1. Impressions must reconcile with reach × frequency within a 5% tolerance.

**Attribution** (`ChannelAttribution`)
Weights must fall within 0–1. Attributed revenue cannot exceed total revenue.

**Incrementality** (`IncrementalityMetrics`)
Incremental conversions cannot exceed total conversions. Incremental revenue is flagged above a 10x ROAS threshold. Test and control cells must each hold at least 100 records.

**Multi-year consistency** (`MultiYearMMM`)
Year-over-year conversion growth is checked against spend growth; a large divergence flags a likely bucketization error. A year dropping to zero after a populated prior year is flagged as a probable misallocation.

---

## Features

**Batch processing** — validate a list of records in one call, with a summary report of pass/fail counts and per-record failure detail.

```python
report = validator.validate_batch(batch_data, 'media_mix')
print(f"Failure rate: {report.failure_rate}")

for failure in report.failures:
    print(f"{failure.record_id}: {failure.errors}")
```

**Strict mode** — for pipelines where a single bad record should halt the run rather than be collected.

```python
validator = DataContractValidator(strict_mode=True)
# Raises DataContractViolation on the first failure
```

**Audit trail** — every validation attempt is logged with timestamp, record ID, outcome, and error detail, exportable to JSON.

```python
trail = validator.get_audit_trail()
validator.export_audit_trail('audit_log.json')
```

**Extensibility** — register additional schemas at runtime.

```python
validator.register_schema('custom_metric', CustomMetricSchema)
```

---

## Installation

```bash
pip install -r requirements.txt
```

Requires Python 3.9+ and Pydantic 2.x.

---

## Project Structure

```
llm-data-governance-guardrails/
│
├── README.md
├── requirements.txt
├── LICENSE
│
├── guardrails/
│   ├── __init__.py
│   ├── metrics.py              # Schema definitions
│   ├── schema_validator.py     # Validator and registry
│   └── exceptions.py           # Custom exceptions
│
├── tests/
│   ├── __init__.py
│   └── test_validator.py       # 26 tests
│
└── examples/
    └── example_usage.py        # 8 usage patterns
```

---

## Running Tests

```bash
python -m pytest tests/ -v
```

26 tests, all passing. The test names describe the specific hallucination each one catches — the suite doubles as documentation of what the framework is for.

```
tests/test_validator.py::TestMediaMixMetrics::test_spend_exceeds_budget_hallucination PASSED
tests/test_validator.py::TestMultiYearMMM::test_yoy_conversion_growth_exceeds_spend_growth PASSED
tests/test_validator.py::TestIncrementalityMetrics::test_incremental_conversions_exceed_total_hallucination PASSED
...
26 passed
```

---

## Running Examples

```bash
python examples/example_usage.py
```

Walks through single-record validation, three distinct hallucination catches, batch validation with reporting, strict mode, audit trail export, a production integration pattern, and the schema registry.

---

## Integration Pattern

```
LLM / model output
        ↓
  Guardrails validator
        ↓
   ┌────┴────┐
 passed    failed
   ↓          ↓
  BI      alert + audit log
```

```python
model_output = generate_mmm_forecast()
result = validator.validate(model_output, 'multi_year_mmm', 'forecast_q4')

if result.passed:
    send_to_bi_pipeline(model_output)
else:
    alert_data_team(result.errors)
```

---

## Error Messages

Failures are written to be actionable — they state the violated constraint and the values involved.

```
Spend (150000) exceeds annual budget (100000)
Reach (600000) exceeds addressable universe (500000)
Frequency must be >= 1. Got: 0.5
Attribution weight out of bounds: must be 0-1. Got: 1.25
2023 conversions (4000) show 300% growth but spend only grew 5%.
  Multi-year bucketization error or hallucination.
Incremental conversions (6000) exceed total conversions (5000).
  Impossible result - likely LLM hallucination.
```

---

## Why This Is Worth Building

The argument is about where an error gets caught, not about a modeled dollar figure.

A constraint violation caught at validation time is a failed record and a log line. The same violation caught after it reaches a dashboard is a chain of work: someone notices a number looks off, traces it back through the pipeline, identifies the source, corrects it, and re-communicates to whoever already saw it. If it wasn't noticed, it informed a decision instead.

The framework is a few hundred lines and integrates at a single point in the pipeline. The asymmetry between that cost and the cost of a silent bad number reaching a planning conversation is the case for it.

---

## Scope and Limitations

**Current scope:** rule-based validation of budget, reach/frequency, attribution, incrementality, and multi-year consistency constraints. Thresholds (the 10x ROAS ceiling, the 5% impressions tolerance, the 100-record minimum cell size) are defaults chosen as reasonable starting points and should be tuned to a given business.

**Not yet built:** performance benchmarking at scale, statistical anomaly detection layered on top of the rules, alert integrations, and a UI for reviewing the audit trail.

**Known limitation:** rule-based validation catches constraint violations, not subtle inaccuracies. A number that is wrong but internally consistent will pass. This layer narrows the failure surface; it doesn't eliminate it.

---

## License

MIT.

---

## Author

**Divya Singla** — Analytics and data operations leader working at the intersection of media measurement, data governance, and AI validation.

Built around a premise worth stating directly: governance for LLM-generated analytics isn't about keeping models out of the reporting stack. It's about validating what they produce before it becomes someone's decision.
