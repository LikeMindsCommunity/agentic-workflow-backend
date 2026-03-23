"""
Data models for the platform knowledge base.
These represent the structured output that Layer 1 produces.
"""
from dataclasses import dataclass, field, asdict
from typing import Optional
import json


@dataclass
class FieldRule:
    """Rules and constraints for a single field in the artifact schema."""
    field_path: str  # e.g. "workflow.nodes[].type"
    data_type: str  # string, number, boolean, array, object, enum
    required: bool
    description: str
    valid_values: list[str] = field(default_factory=list)  # for enums
    default_value: Optional[str] = None
    depends_on: Optional[str] = None  # field path this depends on
    constraints: list[str] = field(default_factory=list)  # free-text rules
    confidence: float = 1.0  # 0-1, how confident we are about this field
    source: str = ""  # where this info came from: "artifact_analysis", "documentation", "client_answer"


@dataclass
class ObjectDefinition:
    """A top-level object/entity in the platform."""
    name: str
    description: str
    fields: list[FieldRule] = field(default_factory=list)
    relationships: list[str] = field(default_factory=list)  # references to other objects
    confidence: float = 1.0


@dataclass
class DependencyRule:
    """Ordering constraint: what must exist before what."""
    source_object: str
    target_object: str
    relationship: str  # "must_exist_before", "references", "contains"
    description: str


@dataclass
class ValidationRule:
    """A cross-cutting validation rule that spans multiple fields or objects."""
    rule_id: str
    description: str
    scope: list[str]  # which objects/fields this rule applies to
    severity: str  # "error" or "warning"
    confidence: float = 1.0


@dataclass
class KnowledgeBase:
    """Complete knowledge base entry for a single platform/artifact type."""
    platform_name: str
    artifact_type: str  # e.g. "IVR Workflow JSON", "Campaign Config"
    artifact_description: str
    objects: list[ObjectDefinition] = field(default_factory=list)
    dependencies: list[DependencyRule] = field(default_factory=list)
    validation_rules: list[ValidationRule] = field(default_factory=list)
    common_patterns: list[dict] = field(default_factory=list)
    gaps: list[dict] = field(default_factory=list)  # unresolved questions
    metadata: dict = field(default_factory=dict)

    def overall_confidence(self) -> float:
        """Average confidence across all fields and rules."""
        scores = []
        for obj in self.objects:
            scores.append(obj.confidence)
            for f in obj.fields:
                scores.append(f.confidence)
        for rule in self.validation_rules:
            scores.append(rule.confidence)
        return sum(scores) / len(scores) if scores else 0.0

    def get_low_confidence_items(self, threshold: float = 0.8) -> list[dict]:
        """Return all items below confidence threshold."""
        items = []
        for obj in self.objects:
            if obj.confidence < threshold:
                items.append({"type": "object", "name": obj.name, "confidence": obj.confidence})
            for f in obj.fields:
                if f.confidence < threshold:
                    items.append({
                        "type": "field",
                        "object": obj.name,
                        "field": f.field_path,
                        "confidence": f.confidence,
                        "current_info": f.description
                    })
        return items

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def save(self, path: str):
        with open(path, "w") as f:
            f.write(self.to_json())

    @classmethod
    def from_dict(cls, data: dict) -> "KnowledgeBase":
        """Reconstruct from dict (for loading from JSON)."""
        kb = cls(
            platform_name=data["platform_name"],
            artifact_type=data["artifact_type"],
            artifact_description=data.get("artifact_description", ""),
            metadata=data.get("metadata", {})
        )
        for obj_data in data.get("objects", []):
            fields = [FieldRule(**f) for f in obj_data.get("fields", [])]
            obj = ObjectDefinition(
                name=obj_data["name"],
                description=obj_data["description"],
                fields=fields,
                relationships=obj_data.get("relationships", []),
                confidence=obj_data.get("confidence", 1.0)
            )
            kb.objects.append(obj)
        for dep_data in data.get("dependencies", []):
            kb.dependencies.append(DependencyRule(**dep_data))
        for rule_data in data.get("validation_rules", []):
            kb.validation_rules.append(ValidationRule(**rule_data))
        kb.common_patterns = data.get("common_patterns", [])
        kb.gaps = data.get("gaps", [])
        return kb
