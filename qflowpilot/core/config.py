
"""
Central configuration management for QFlowPilot.

Supports:
- Shot budget configuration
- Quality requirements
- Backend selection
- Runtime execution settings
- YAML loading and saving

This module is independent of Qiskit and backend implementations.
"""

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


# ---------------------------------------------------------
# 1. Shot configuration
# ---------------------------------------------------------

@dataclass
class ShotConfig:
    """Controls the measurement shot budget."""

    initial_shots: int = 1024
    min_shots: int = 100
    max_shots: int = 100000
    additional_shots: int = 1024

    def __post_init__(self) -> None:
        for name in (
            "initial_shots",
            "min_shots",
            "max_shots",
            "additional_shots",
        ):
            value = getattr(self, name)

            if not isinstance(value, int) or isinstance(value, bool):
                raise TypeError(f"{name} must be an integer.")

            if value <= 0:
                raise ValueError(f"{name} must be greater than zero.")

        if self.min_shots > self.max_shots:
            raise ValueError("min_shots cannot exceed max_shots.")

        if not self.min_shots <= self.initial_shots <= self.max_shots:
            raise ValueError(
                "initial_shots must be between min_shots and max_shots."
            )


# ---------------------------------------------------------
# 2. Quality configuration
# ---------------------------------------------------------

@dataclass
class QualityConfig:
    """
    Defines quality requirements for runtime decisions.

    Application score and success probability are separate
    measures. Their meaning depends on the workload.
    """

    confidence_level: float = 0.95

    min_success_probability: Optional[float] = None
    min_application_score: Optional[float] = None
    max_standard_error: Optional[float] = None

    def __post_init__(self) -> None:
        if not 0.0 < self.confidence_level < 1.0:
            raise ValueError(
                "confidence_level must be between 0 and 1."
            )

        if self.min_success_probability is not None:
            if not 0.0 <= self.min_success_probability <= 1.0:
                raise ValueError(
                    "min_success_probability must be between 0 and 1."
                )

        if self.min_application_score is not None:
            if not 0.0 <= self.min_application_score <= 1.0:
                raise ValueError(
                    "min_application_score must be between 0 and 1."
                )

        if self.max_standard_error is not None:
            if self.max_standard_error <= 0:
                raise ValueError(
                    "max_standard_error must be greater than zero."
                )


# ---------------------------------------------------------
# 3. Backend configuration
# ---------------------------------------------------------

@dataclass
class BackendConfig:
    """
    Selects the execution backend.

    Supported execution modes correspond to ExecutionMode
    in core/models.py.
    """

    execution_mode: str = "ideal_simulator"
    backend_name: str = "aer_simulator"

    optimization_level: int = 1
    transpilation_enabled: bool = True

    def __post_init__(self) -> None:
        supported_modes = {
            "ideal_simulator",
            "noisy_simulator",
            "quantum_hardware",
            "classical",
        }

        if self.execution_mode not in supported_modes:
            raise ValueError(
                f"Unsupported execution_mode: {self.execution_mode}. "
                f"Choose one of {sorted(supported_modes)}."
            )

        if not self.backend_name.strip():
            raise ValueError("backend_name cannot be empty.")

        if (
            not isinstance(self.optimization_level, int)
            or isinstance(self.optimization_level, bool)
        ):
            raise TypeError("optimization_level must be an integer.")

        if self.optimization_level not in range(4):
            raise ValueError(
                "optimization_level must be between 0 and 3."
            )

        if not isinstance(self.transpilation_enabled, bool):
            raise TypeError("transpilation_enabled must be a boolean.")


# ---------------------------------------------------------
# 4. Runtime configuration
# ---------------------------------------------------------

@dataclass
class RuntimeConfig:
    """Controls runtime execution behavior."""

    execution_timeout_s: float = 300.0
    max_retries: int = 2
    retry_delay_s: float = 1.0

    random_seed: Optional[int] = 42

    fail_fast: bool = True
    collect_metrics: bool = True

    def __post_init__(self) -> None:
        if self.execution_timeout_s <= 0:
            raise ValueError(
                "execution_timeout_s must be greater than zero."
            )

        if (
            not isinstance(self.max_retries, int)
            or isinstance(self.max_retries, bool)
        ):
            raise TypeError("max_retries must be an integer.")

        if self.max_retries < 0:
            raise ValueError("max_retries cannot be negative.")

        if self.retry_delay_s < 0:
            raise ValueError("retry_delay_s cannot be negative.")

        if self.random_seed is not None:
            if (
                not isinstance(self.random_seed, int)
                or isinstance(self.random_seed, bool)
            ):
                raise TypeError("random_seed must be an integer or None.")

            if self.random_seed < 0:
                raise ValueError("random_seed cannot be negative.")

        if not isinstance(self.fail_fast, bool):
            raise TypeError("fail_fast must be a boolean.")

        if not isinstance(self.collect_metrics, bool):
            raise TypeError("collect_metrics must be a boolean.")


# ---------------------------------------------------------
# 5. Complete QFlowPilot configuration
# ---------------------------------------------------------

@dataclass
class QFlowPilotConfig:
    """
    Main configuration object.

    Combines shot, quality, backend and runtime settings.
    """

    shots: ShotConfig = field(default_factory=ShotConfig)
    quality: QualityConfig = field(default_factory=QualityConfig)
    backend: BackendConfig = field(default_factory=BackendConfig)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QFlowPilotConfig":
        """Build configuration from a dictionary."""

        if not isinstance(data, dict):
            raise TypeError("Configuration must be a dictionary.")

        allowed_sections = {
            "shots",
            "quality",
            "backend",
            "runtime",
        }

        unknown_sections = set(data) - allowed_sections

        if unknown_sections:
            raise ValueError(
                f"Unknown configuration sections: "
                f"{sorted(unknown_sections)}"
            )

        def build_section(section_name, section_class):
            section_data = data.get(section_name, {})

            if not isinstance(section_data, dict):
                raise TypeError(
                    f"Configuration section '{section_name}' "
                    "must be a dictionary."
                )

            allowed_fields = set(section_class.__dataclass_fields__)
            unknown_fields = set(section_data) - allowed_fields

            if unknown_fields:
                raise ValueError(
                    f"Unknown fields in '{section_name}': "
                    f"{sorted(unknown_fields)}"
                )

            return section_class(**section_data)

        return cls(
            shots=build_section("shots", ShotConfig),
            quality=build_section("quality", QualityConfig),
            backend=build_section("backend", BackendConfig),
            runtime=build_section("runtime", RuntimeConfig),
        )

    @classmethod
    def from_yaml(cls, file_path: str) -> "QFlowPilotConfig":
        """Load configuration from a YAML file."""

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {path}"
            )

        with path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file)

        if data is None:
            data = {}

        if not isinstance(data, dict):
            raise TypeError(
                "YAML configuration must contain a mapping."
            )

        return cls.from_dict(data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration into a dictionary."""

        return asdict(self)

    def to_yaml(self, file_path: str) -> None:
        """Save configuration to a YAML file."""

        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", encoding="utf-8") as file:
            yaml.safe_dump(
                self.to_dict(),
                file,
                sort_keys=False,
                default_flow_style=False,
            )
