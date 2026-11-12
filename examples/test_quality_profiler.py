from qflowpilot.profiler.quality_profiler import QualityProfiler

profiler = QualityProfiler(
    max_standard_error=0.05
)

counts = {
    "00": 500,
    "11": 524,
}

observable_values = {
    "00": 0.0,
    "11": 1.0,
}

reference_distribution = {
    "00": 0.5,
    "11": 0.5,
}

result = profiler.estimate_from_counts(
    counts=counts,
    observable_values=observable_values,
    confidence_level=0.95,
    reference_distribution=reference_distribution,
)

print("Expectation:", result.expectation_value)
print("Variance:", result.variance)
print("Standard error:", result.standard_error)
print("Confidence interval:", result.confidence_interval)
print(
    "TVD:",
    result.metadata["total_variation_distance"],
)
print("Quality satisfied:", result.quality_satisfied)