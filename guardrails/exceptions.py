"""
Custom exceptions for MMM data governance guardrails.

Distinguishes between:
- Data contract violations (schema failure)
- Hallucinations (logical impossibilities)
- Schema not found errors
"""


class GuardrailException(Exception):
    """Base exception for all guardrail errors."""
    pass


class DataContractViolation(GuardrailException):
    """
    Raised when data fails schema validation.
    
    Example:
        - Spend < 0
        - Reach > universe
        - Spend > annual budget
    """
    pass


class HalluccinationDetected(GuardrailException):
    """
    Raised when data violates business logic/constraints.
    
    This is a stricter category than DataContractViolation.
    Indicates LLM likely invented data.
    
    Example:
        - 2024 conversions but 2023 was 0 (bucketing error)
        - Incremental lift > total conversions (impossible)
        - Attribution weight > 100% (impossible)
        - Conversion growth 300% but spend only 5% (hallucination)
    """
    pass


class SchemaNotFound(GuardrailException):
    """
    Raised when requested schema is not in registry.
    
    Available schemas must be registered before use.
    """
    pass
