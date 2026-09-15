"""
DataContractValidator: Main orchestrator for MMM validation.

Handles:
- Single record validation
- Batch validation with detailed reporting
- Schema registry for extensibility
- Audit trail logging
"""

from pydantic import BaseModel, ValidationError
from typing import Any, Dict, List, Type, Optional
from datetime import datetime
import json
from .metrics import (
    MediaMixMetrics,
    ReachAndFrequency,
    ChannelAttribution,
    IncrementalityMetrics,
    MultiYearMMM,
    MMMAuditTrail,
)
from .exceptions import DataContractViolation, HalluccinationDetected, SchemaNotFound


class ValidationResult(BaseModel):
    """Result of a single validation attempt."""
    passed: bool
    record_id: str
    schema_type: str
    errors: List[str] = []
    data_snapshot: Dict[str, Any]


class BatchValidationReport(BaseModel):
    """Summary report for batch validation."""
    total_records: int
    passed_count: int
    failed_count: int
    failure_rate: float
    failures: List[ValidationResult] = []
    audit_trail: List[Dict[str, Any]] = []


class DataContractValidator:
    """
    Main validator for MMM data contracts.
    
    Enforces schema validation and catches:
    - Budget math violations
    - Multi-year bucketization errors
    - Reach/frequency impossibilities
    - Attribution logic violations
    - Incrementality hallucinations
    """
    
    def __init__(self, strict_mode: bool = False):
        """
        Initialize validator.
        
        Args:
            strict_mode: If True, stop on first validation failure. 
                        If False, collect all failures.
        """
        self.strict_mode = strict_mode
        self.audit_trail: List[Dict[str, Any]] = []
        
        # Schema registry
        self.schemas: Dict[str, Type[BaseModel]] = {
            'media_mix': MediaMixMetrics,
            'reach_frequency': ReachAndFrequency,
            'channel_attribution': ChannelAttribution,
            'incrementality': IncrementalityMetrics,
            'multi_year_mmm': MultiYearMMM,
        }
    
    def register_schema(self, name: str, schema: Type[BaseModel]) -> None:
        """Register a custom schema."""
        self.schemas[name] = schema
    
    def validate(
        self,
        data: Dict[str, Any],
        schema_type: str,
        record_id: Optional[str] = None,
    ) -> ValidationResult:
        """
        Validate a single record.
        
        Args:
            data: Record data as dictionary
            schema_type: Type of schema to validate against
            record_id: Optional ID for audit trail
            
        Returns:
            ValidationResult with pass/fail and error details
            
        Raises:
            SchemaNotFound: If schema_type not registered
            DataContractViolation: If strict_mode=True and validation fails
        """
        if schema_type not in self.schemas:
            raise SchemaNotFound(f"Schema '{schema_type}' not found in registry")
        
        schema = self.schemas[schema_type]
        record_id = record_id or str(data.get('id', 'unknown'))
        
        try:
            # Attempt validation
            schema(**data)
            
            # Log success
            self._log_audit(
                record_id=record_id,
                schema_type=schema_type,
                passed=True,
                data_snapshot=data,
            )
            
            return ValidationResult(
                passed=True,
                record_id=record_id,
                schema_type=schema_type,
                data_snapshot=data,
            )
        
        except ValidationError as e:
            # Pydantic returns a list of dicts; pull out the human-readable
            # message and strip Pydantic's "Value error, " prefix so the
            # audit trail reads cleanly.
            errors = []
            for err in e.errors():
                msg = err.get('msg', str(err))
                if msg.startswith('Value error, '):
                    msg = msg[len('Value error, '):]
                field = err.get('loc')
                if field:
                    msg = f"{'.'.join(str(f) for f in field)}: {msg}"
                errors.append(msg)
            
            # Log failure
            self._log_audit(
                record_id=record_id,
                schema_type=schema_type,
                passed=False,
                error_message=' | '.join(errors),
                data_snapshot=data,
            )
            
            result = ValidationResult(
                passed=False,
                record_id=record_id,
                schema_type=schema_type,
                errors=errors,
                data_snapshot=data,
            )
            
            if self.strict_mode:
                raise DataContractViolation(
                    f"Record {record_id} failed validation: {errors[0]}"
                )
            
            return result
    
    def validate_batch(
        self,
        batch_data: List[Dict[str, Any]],
        schema_type: str,
    ) -> BatchValidationReport:
        """
        Validate multiple records.
        
        Args:
            batch_data: List of records as dictionaries
            schema_type: Type of schema to validate against
            
        Returns:
            BatchValidationReport with summary and failures
        """
        results = []
        failures = []
        
        for i, record in enumerate(batch_data):
            record_id = record.get('id', f'record_{i}')
            result = self.validate(record, schema_type, record_id)
            results.append(result)
            
            if not result.passed:
                failures.append(result)
        
        total = len(results)
        passed = total - len(failures)
        
        report = BatchValidationReport(
            total_records=total,
            passed_count=passed,
            failed_count=len(failures),
            failure_rate=len(failures) / total if total > 0 else 0.0,
            failures=failures,
            audit_trail=self.audit_trail.copy(),
        )
        
        return report
    
    def detect_hallucination(
        self,
        data: Dict[str, Any],
        schema_type: str,
    ) -> bool:
        """
        Check if data likely contains LLM hallucination.
        
        Returns True if validation fails (hallucination detected).
        """
        try:
            self.validate(data, schema_type)
            return False
        except (DataContractViolation, SchemaNotFound):
            return True
    
    def _log_audit(
        self,
        record_id: str,
        schema_type: str,
        passed: bool,
        data_snapshot: Dict[str, Any],
        error_message: Optional[str] = None,
    ) -> None:
        """Log validation result to audit trail."""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'record_id': record_id,
            'schema_type': schema_type,
            'passed': passed,
            'error_message': error_message,
            'data_snapshot': data_snapshot,
        }
        self.audit_trail.append(entry)
    
    def get_audit_trail(self) -> List[Dict[str, Any]]:
        """Retrieve full audit trail."""
        return self.audit_trail.copy()
    
    def clear_audit_trail(self) -> None:
        """Clear audit trail."""
        self.audit_trail = []
    
    def export_audit_trail(self, filepath: str) -> None:
        """Export audit trail to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.audit_trail, f, indent=2, default=str)


class SchemaRegistry:
    """
    Centralized schema registry for sharing across validators.
    
    Allows runtime registration and lookup of schemas.
    """
    
    _schemas: Dict[str, Type[BaseModel]] = {
        'media_mix': MediaMixMetrics,
        'reach_frequency': ReachAndFrequency,
        'channel_attribution': ChannelAttribution,
        'incrementality': IncrementalityMetrics,
        'multi_year_mmm': MultiYearMMM,
    }
    
    @classmethod
    def register(cls, name: str, schema: Type[BaseModel]) -> None:
        """Register a schema globally."""
        cls._schemas[name] = schema
    
    @classmethod
    def get(cls, name: str) -> Type[BaseModel]:
        """Retrieve a schema."""
        if name not in cls._schemas:
            raise SchemaNotFound(f"Schema '{name}' not registered")
        return cls._schemas[name]
    
    @classmethod
    def list_schemas(cls) -> List[str]:
        """List all registered schemas."""
        return list(cls._schemas.keys())
