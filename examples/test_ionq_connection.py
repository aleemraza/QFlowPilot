import os
from pathlib import Path
from dotenv import load_dotenv
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

print("IonQ API key found:", bool(IONQ_API_KEY))
provider = IonQProvider(token=IONQ_API_KEY)
print("\nAvailable provider backends:")
for backend in provider.backends():
    print(backend.name)

# Check the production Forte target
forte = provider.get_backend("ionq_qpu.forte-1")

print("\nForte backend:")
print("Name:", forte.name)
print("Qubits:", forte.num_qubits)
print("Status:", forte.status())

# Check the simulator
simulator = provider.get_backend("ionq_simulator")

print("\nIdeal simulator:")
print("Name:", simulator.name)
print("Qubits:", simulator.num_qubits)
print("Status:", simulator.status())

# Check hardware-noise simulator configurations
for noise in ["forte-1", "aria-1"]:
    simulator.set_options(noise_model=noise)
    print(f"\nConfigured noise model: {noise}")
