
from qflowpilot.core.config import QFlowPilotConfig

# Load experiment settings
config = QFlowPilotConfig.from_yaml(
    "experiments/configs/noisy_simulation.yaml"
)

# Access shot settings
print("Initial shots:", config.shots.initial_shots)
print("Maximum shots:", config.shots.max_shots)

# Access quality requirements
print(
    "Minimum application score:",
    config.quality.min_application_score
)

# Access backend settings
print("Execution mode:", config.backend.execution_mode)
print("Backend:", config.backend.backend_name)

# Access runtime settings
print("Timeout:", config.runtime.execution_timeout_s)
print("Maximum retries:", config.runtime.max_retries)
