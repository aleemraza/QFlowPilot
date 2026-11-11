import os
from pathlib import Path
from dotenv import load_dotenv
from qflowpilot.adapters.ionq_adapter import IonQAdapter
from importlib.metadata import version
from qiskit_ionq import IonQProvider

# Locate the QFlowPilot project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]
# print(PROJECT_ROOT)
# Load environment variables from project .env
load_dotenv(PROJECT_ROOT / ".env")
# print(load_dotenv)
IONQ_API_KEY = os.getenv("IONQ_API_KEY")
# print(IONQ_API_KEY)

if not IONQ_API_KEY:
    raise RuntimeError("IONQ_API_KEY was not found in the .env file.")
targets = [
    "ideal_simulator",
    "forte_noisy_simulator",
    "aria_noisy_simulator",
    "forte_qpu",
]

for target in targets:
    print(f"\nTesting: {target}")

    try:
        adapter = IonQAdapter(
            target=target,
            token=IONQ_API_KEY,
        )
        print(adapter.get_backend_info())
    except Exception as exc:
        print(f"FAILED: {exc}")
