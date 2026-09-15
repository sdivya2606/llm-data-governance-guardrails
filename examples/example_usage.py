"""
Real-world usage patterns for MMM data governance guardrails.

Demonstrates:
1. Single record validation
2. Catching a budget hallucination
3. Catching a multi-year bucketization error
4. Batch validation with reporting
5. Strict mode (fail-fast for critical pipelines)
6. Audit trail for compliance
7. Production integration pattern
"""

import sys
from pathlib import Path

# Make the repo root importable so this script runs standalone,
# regardless of the directory it's invoked from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from guardrails.schema_validator import DataContractValidator, SchemaRegistry
from guardrails.exceptions import DataContractViolation
import json


def print_section(title):
    """Print a formatted section header."""
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


# ============================================================================
# EXAMPLE 1: Validate Single Media Mix Record
# ============================================================================

def example_1_single_record():
    print_section("EXAMPLE 1: Validate Single Media Mix Record")
    
    validator = DataContractValidator()
    
    # Clean data
    clean_record = {
        'year': 2024,
        'channel': 'paid_search',
        'spend': 50000,
        'impressions': 1000000,
        'annual_budget': 100000,
    }
    
    result = validator.validate(clean_record, 'media_mix', 'paidSearch_Q4')
    
    print(f"\n✓ Record ID: {result.record_id}")
    print(f"✓ Schema: {result.schema_type}")
    print(f"✓ Validation: {'PASSED' if result.passed else 'FAILED'}")
    print(f"✓ Errors: {result.errors if result.errors else 'None'}")


# ============================================================================
# EXAMPLE 2: Catch Budget Hallucination
# ============================================================================

def example_2_budget_hallucination():
    print_section("EXAMPLE 2: Catch Budget Hallucination")
    print("Scenario: LLM incorrectly allocates $150k spend to $100k budget")
    
    validator = DataContractValidator()
    
    # Hallucinated data: spend > budget
    hallucinated_record = {
        'year': 2024,
        'channel': 'display',
        'spend': 150000,  # Exceeds annual budget
        'impressions': 2000000,
        'annual_budget': 100000,
    }
    
    result = validator.validate(hallucinated_record, 'media_mix', 'display_Q4')
    
    print(f"\n✗ Record ID: {result.record_id}")
    print(f"✗ Validation: {'PASSED' if result.passed else 'CAUGHT HALLUCINATION'}")
    print(f"✗ Error Details:")
    for error in result.errors:
        print(f"  - {error}")
    
    print(f"\n→ Guardrail blocked impossible budget allocation before pipeline")


# ============================================================================
# EXAMPLE 3: Catch Multi-Year Bucketization Error
# ============================================================================

def example_3_multiyear_error():
    print_section("EXAMPLE 3: Catch Multi-Year Bucketization Error")
    print("Scenario: 2024 spend allocated to 2022 cohort + impossible growth")
    
    validator = DataContractValidator()
    
    # Hallucinated data: conversion growth (300%) >> spend growth (5%)
    hallucinated_record = {
        'cohort_year': 2023,
        'channel': 'social',
        'spend_2022': 100000,
        'spend_2023': 105000,  # Only 5% growth
        'spend_2024': 110000,
        'conversions_2022': 1000,
        'conversions_2023': 4000,  # 300% growth: impossible without spend increase
        'conversions_2024': 4500,
    }
    
    result = validator.validate(hallucinated_record, 'multi_year_mmm', 'social_cohort_2023')
    
    print(f"\n✗ Record ID: {result.record_id}")
    print(f"✗ Validation: {'PASSED' if result.passed else 'CAUGHT HALLUCINATION'}")
    print(f"✗ Error Details:")
    for error in result.errors:
        print(f"  - {error}")
    
    print(f"\n→ Guardrail detected impossible YoY growth pattern")


# ============================================================================
# EXAMPLE 4: Batch Validation with Reporting
# ============================================================================

def example_4_batch_validation():
    print_section("EXAMPLE 4: Batch Validation with Reporting")
    print("Scenario: Validate 5 channel records from MMM model output")
    
    validator = DataContractValidator()
    
    # Mix of valid and invalid records
    batch_data = [
        {
            'year': 2024,
            'channel': 'paid_search',
            'spend': 50000,
            'impressions': 1000000,
            'annual_budget': 200000,
        },
        {
            'year': 2024,
            'channel': 'display',
            'spend': 30000,
            'impressions': 500000,
            'annual_budget': 200000,
        },
        {
            'year': 2024,
            'channel': 'social',
            'spend': 250000,  # HALLUCINATION: exceeds budget
            'impressions': 800000,
            'annual_budget': 200000,
        },
        {
            'year': 2024,
            'channel': 'video',
            'spend': 40000,
            'impressions': 200000,
            'annual_budget': 200000,
        },
        {
            'year': 2024,
            'channel': 'email',
            'spend': 10000,
            'impressions': 500000,
            'annual_budget': 200000,
        },
    ]
    
    report = validator.validate_batch(batch_data, 'media_mix')
    
    print(f"\n📊 Batch Validation Report")
    print(f"   Total Records: {report.total_records}")
    print(f"   Passed: {report.passed_count}")
    print(f"   Failed: {report.failed_count}")
    print(f"   Failure Rate: {report.failure_rate * 100:.1f}%")
    
    if report.failures:
        print(f"\n⚠ Failed Records:")
        for failure in report.failures:
            print(f"\n   Record: {failure.record_id}")
            for error in failure.errors:
                print(f"   Error: {error}")


# ============================================================================
# EXAMPLE 5: Strict Mode (Fail-Fast for Critical Pipelines)
# ============================================================================

def example_5_strict_mode():
    print_section("EXAMPLE 5: Strict Mode (Fail-Fast)")
    print("Scenario: Critical BI pipeline requires immediate failure on errors")
    
    # Initialize validator in strict mode
    validator = DataContractValidator(strict_mode=True)
    
    hallucinated_record = {
        'channel': 'social',
        'reach': 600000,
        'frequency': 1.5,
        'addressable_universe': 500000,  # HALLUCINATION: reach > universe
        'impressions': 900000,
    }
    
    try:
        result = validator.validate(hallucinated_record, 'reach_frequency', 'social_reach')
        print("✓ Record validated successfully")
    except DataContractViolation as e:
        print(f"\n✗ Strict Mode: Pipeline STOPPED")
        print(f"✗ Error: {str(e)}")
        print(f"✗ Impact: Prevents downstream data quality issues")


# ============================================================================
# EXAMPLE 6: Audit Trail for Compliance
# ============================================================================

def example_6_audit_trail():
    print_section("EXAMPLE 6: Audit Trail for Compliance")
    print("Scenario: Enterprise needs validation audit for reporting")
    
    validator = DataContractValidator()
    
    # Validate several records
    records = [
        {
            'year': 2024,
            'channel': 'paid_search',
            'spend': 50000,
            'impressions': 1000000,
            'annual_budget': 100000,
        },
        {
            'year': 2024,
            'channel': 'display',
            'spend': 150000,  # Fails
            'impressions': 500000,
            'annual_budget': 100000,
        },
    ]
    
    for i, record in enumerate(records):
        validator.validate(record, 'media_mix', f'record_{i+1}')
    
    # Export audit trail
    trail = validator.get_audit_trail()
    
    print(f"\n📋 Validation Audit Trail ({len(trail)} entries)")
    for entry in trail:
        status = "✓ PASS" if entry['passed'] else "✗ FAIL"
        print(f"\n   {status} | Record: {entry['record_id']} | Schema: {entry['schema_type']}")
        if entry['error_message']:
            print(f"        Error: {entry['error_message'][:80]}...")


# ============================================================================
# EXAMPLE 7: Production Integration Pattern
# ============================================================================

def example_7_production_integration():
    print_section("EXAMPLE 7: Production Integration Pattern")
    print("Scenario: LLM output → Guardrails → BI Pipeline")
    
    validator = DataContractValidator(strict_mode=False)
    
    # Simulate LLM output for multi-year MMM
    llm_output = {
        'cohort_year': 2024,
        'channel': 'paid_search',
        'spend_2022': 100000,
        'spend_2023': 110000,
        'spend_2024': 120000,
        'conversions_2022': 10000,
        'conversions_2023': 11000,
        'conversions_2024': 12000,
    }
    
    # Validate before sending to BI
    result = validator.validate(llm_output, 'multi_year_mmm', 'llm_output_2024')
    
    if result.passed:
        print(f"\n✓ LLM Output Valid")
        print(f"✓ Guardrails Passed: Data safe to send to BI")
        print(f"✓ Pipeline Continue: ✓")
    else:
        print(f"\n✗ LLM Output Invalid")
        print(f"✗ Guardrails Failed: Data blocked from BI")
        for error in result.errors:
            print(f"✗ Reason: {error}")
        print(f"✗ Action: Alert data team, investigate LLM prompt")


# ============================================================================
# EXAMPLE 8: Schema Registry for Extensibility
# ============================================================================

def example_8_schema_registry():
    print_section("EXAMPLE 8: Schema Registry (Extensibility)")
    print("Scenario: Check available schemas and register custom one")
    
    # List all registered schemas
    schemas = SchemaRegistry.list_schemas()
    print(f"\nAvailable Schemas:")
    for schema in schemas:
        print(f"  - {schema}")
    
    print(f"\nTotal: {len(schemas)} schemas registered")
    print(f"Custom schemas can be added at runtime via: validator.register_schema()")


# ============================================================================
# MAIN: Run All Examples
# ============================================================================

if __name__ == '__main__':
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " MMM DATA GOVERNANCE GUARDRAILS - USAGE EXAMPLES ".center(58) + "║")
    print("╚" + "═" * 58 + "╝")
    
    example_1_single_record()
    example_2_budget_hallucination()
    example_3_multiyear_error()
    example_4_batch_validation()
    example_5_strict_mode()
    example_6_audit_trail()
    example_7_production_integration()
    example_8_schema_registry()
    
    print("\n" + "=" * 60)
    print("All examples completed")
    print("=" * 60 + "\n")
