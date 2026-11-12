
# from datetime import datetime, timedelta, timezone

# from qflowpilot.profiler.latency_profiler import LatencyProfiler


# def main():
#     profiler = LatencyProfiler()

#     print("=" * 60)
#     print("LATENCY PROFILER TEST")
#     print("=" * 60)

#     # -----------------------------------
#     # Equation 14: Latency decomposition
#     # -----------------------------------

#     breakdown = profiler.profile_latency_breakdown(
#         compilation_time_s=2.0,
#         queue_time_s=5.0,
#         qpu_execution_time_s=8.0,
#         postprocessing_time_s=1.5,
#         communication_time_s=1.0,
#         observed_e2e_latency_s=17.5,
#     )

#     print("\nLATENCY BREAKDOWN")
#     print("Compilation:", breakdown.compilation_time_s)
#     print("Queue:", breakdown.queue_time_s)
#     print("QPU execution:", breakdown.qpu_execution_time_s)
#     print("Post-processing:", breakdown.postprocessing_time_s)
#     print("Communication:", breakdown.communication_time_s)
#     print("Total latency:", breakdown.total_latency_s)
#     print("Decomposition error:", breakdown.decomposition_error_s)

#     # -----------------------------------
#     # Equation 15: Iterative workload
#     # -----------------------------------

#     iterative = profiler.profile_iterative(
#         round_latencies_s=[10.0, 12.0, 9.0, 11.0, 8.0],
#         workload_id="qaoa_iterative_001",
#     )

#     print("\nITERATIVE WORKLOAD")
#     print("Rounds:", iterative.number_of_executions)
#     print("Total latency:", iterative.total_latency_s)
#     print("Average round latency:", iterative.average_execution_latency_s)

#     # -----------------------------------
#     # Equation 16: Batch makespan
#     # -----------------------------------

#     batch_start = datetime.now(timezone.utc)

#     completion_times = [
#         batch_start + timedelta(seconds=10),
#         batch_start + timedelta(seconds=15),
#         batch_start + timedelta(seconds=12),
#         batch_start + timedelta(seconds=8),
#     ]

#     batch = profiler.profile_batch(
#         batch_start=batch_start,
#         completion_times=completion_times,
#         workload_id="qaoa_batch_001",
#     )

#     print("\nBATCH WORKLOAD")
#     print("Number of jobs:", batch.number_of_executions)
#     print("Batch makespan:", batch.total_latency_s)

#     # -----------------------------------
#     # Summary statistics
#     # -----------------------------------

#     print("\nLATENCY SUMMARY")
#     print(
#         profiler.summarize(
#             profiles=[],
#             metric="end_to_end_latency_s",
#         )
#     )

#     print("\nAll example calculations completed.")


# if __name__ == "__main__":
#     main()


from datetime import datetime, timedelta, timezone

from qflowpilot.core.models import (
    ExecutionResult,
    ExecutionStatus,
    ExecutionMode,
)
from qflowpilot.profiler.latency_profiler import LatencyProfiler

start = datetime.now(timezone.utc)

result = ExecutionResult(
    result_id="result_001",
    request_id="request_001",
    status=ExecutionStatus.COMPLETED,
    shots=1024,
    backend_name="aer_ideal",
    execution_mode=ExecutionMode.IDEAL_SIMULATOR,
    submitted_at=start,
    started_at=start + timedelta(seconds=5),
    completed_at=start + timedelta(seconds=13),
)

profiler = LatencyProfiler()
profile = profiler.profile_execution(result)

print("Queue latency:", profile.queue_latency_s)
print("QPU execution latency:", profile.qpu_execution_latency_s)
print("End-to-end latency:", profile.end_to_end_latency_s)
