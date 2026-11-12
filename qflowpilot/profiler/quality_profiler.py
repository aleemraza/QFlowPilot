from __future__ import annotations
import math
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from statistics import NormalDist
from typing import Any, Dict, Optional, Tuple
from qflowpilot.core.models import QualityEstimate


class QualityProfiler:
    """
    Estimate quantum measurement quality and compare measurement
    distributions against an optional reference distribution.

    Implemented equations
    ---------------------
    (1) Empirical measurement probability
        P_hat(x) = n_x / N

    (2) Probability normalization
        sum_x P_hat(x) = 1

    (3) Observable expectation
        mu_hat = sum_x o(x) P_hat(x)

    (4) Observable variance
        sigma_hat^2 = sum_x P_hat(x) * (o(x) - mu_hat)^2

    (5) Standard error
        SE(mu_hat) = sigma_hat / sqrt(N)

    (6) Approximate confidence interval
        CI = mu_hat +/- z * SE(mu_hat)

    (7) Total variation distance
        TVD(P, Q) = 0.5 * sum_x |P(x) - Q(x)|

    Notes
    -----
    - Equations (1)-(6) can be calculated from measurement counts and
      an observable-value mapping.
    - Equation (7) requires a reference probability distribution.
    - A reference distribution should not be assumed to be available
      during real quantum hardware execution.
    - Application-specific ground truth evaluation is not performed
      automatically by this class.
    """

    def __init__(
        self,
        max_standard_error: Optional[float] = None,
        min_success_probability: Optional[float] = None,
        min_application_score: Optional[float] = None,
    ) -> None:
        self.max_standard_error = self._validate_optional_nonnegative(
            max_standard_error,
            "max_standard_error",
        )

        self.min_success_probability = self._validate_optional_probability(
            min_success_probability,
            "min_success_probability",
        )

        self.min_application_score = min_application_score

    # ---------------------------------------------------------
    # Public method 1: Estimate quality from observable samples
    # ---------------------------------------------------------

    def estimate_from_samples(
        self,
        samples: Sequence[float],
        confidence_level: float = 0.95,
        success_predicate: Optional[Callable[[float], bool]] = None,
        score_function: Optional[Callable[[float], float]] = None,
    ) -> QualityEstimate:
        """
        Estimate measurement statistics from numerical observable samples.

        Parameters
        ----------
        samples:
            Observable measurement outcomes, one value per shot.

        confidence_level:
            Confidence level for the normal-approximation interval.

        success_predicate:
            Optional function that returns True for a successful sample.

        score_function:
            Optional function that converts each sample into an
            application score.

        Returns
        -------
        QualityEstimate
            Statistical quality estimates and validation metadata.
        """

        values = self._validate_numeric_samples(samples)
        self._validate_confidence_level(confidence_level)

        number_of_samples = len(values)

        mean = sum(values) / number_of_samples

        # Equation 4: empirical population variance.
        variance = sum(
            (value - mean) ** 2 for value in values
        ) / number_of_samples

        # Equation 5: standard error.
        standard_error = math.sqrt(variance / number_of_samples)

        # Equation 6: normal-approximation confidence interval.
        confidence_interval = self._normal_confidence_interval(
            mean,
            standard_error,
            confidence_level,
        )

        success_probability = None
        success_interval = None

        if success_predicate is not None:
            successful_samples = sum(
                1 for value in values if success_predicate(value)
            )

            success_probability = (
                successful_samples / number_of_samples
            )

            success_interval = self._wilson_interval(
                successful_samples,
                number_of_samples,
                confidence_level,
            )

        application_score = None

        if score_function is not None:
            scores = [
                self._validate_finite_number(
                    score_function(value),
                    "application score",
                )
                for value in values
            ]

            application_score = sum(scores) / number_of_samples

        quality_satisfied = self._check_quality_thresholds(
            standard_error=standard_error,
            success_probability=success_probability,
            application_score=application_score,
        )

        return QualityEstimate(
            sample_count=number_of_samples,
            expectation_value=mean,
            variance=variance,
            standard_error=standard_error,
            confidence_interval=confidence_interval,
            success_probability=success_probability,
            application_score=application_score,
            quality_satisfied=quality_satisfied,
            metadata={
                "estimation_method": "observable_samples",
                "confidence_level": confidence_level,
                "confidence_interval_method": "normal_approximation",
                "variance_method": "empirical_population_variance",
                "success_probability_interval": success_interval,
                "thresholds": self._threshold_metadata(),
            },
        )

    # ---------------------------------------------------------
    # Public method 2: Estimate quality from bitstring counts
    # ---------------------------------------------------------

    def estimate_from_counts(
        self,
        counts: Mapping[str, int],
        observable_values: Mapping[str, float],
        confidence_level: float = 0.95,
        success_states: Optional[Sequence[str]] = None,
        score_function: Optional[Callable[[str], float]] = None,
        reference_distribution: Optional[Mapping[str, float]] = None,
    ) -> QualityEstimate:
        """
        Estimate measurement quality from quantum measurement counts.

        Parameters
        ----------
        counts:
            Mapping from measured bitstrings to shot counts.

            Example:
                {"00": 500, "11": 524}

        observable_values:
            Mapping from each measured bitstring to its observable value.

            Example:
                {"00": 0.0, "11": 1.0}

        confidence_level:
            Confidence level for the expectation-value interval.

        success_states:
            Optional bitstrings considered successful by the workload.

        score_function:
            Optional function that maps a bitstring to an application score.

        reference_distribution:
            Optional reference probability distribution for Equation 7.

            Example:
                {"00": 0.5, "11": 0.5}

            This argument is optional because a reference distribution
            may not be available during real hardware execution.

        Returns
        -------
        QualityEstimate
            Measurement statistics, optional success probability,
            optional application score, and optional TVD.
        """

        validated_counts = self._validate_counts(counts)
        self._validate_confidence_level(confidence_level)

        total_shots = sum(validated_counts.values())

        if total_shots <= 0:
            raise ValueError("Total measurement shots must be greater than zero.")

        # Equation 1: empirical measurement probabilities.
        probabilities = {
            bitstring: count / total_shots
            for bitstring, count in validated_counts.items()
        }

        # Equation 2: probability normalization.
        probability_sum = sum(probabilities.values())

        if not math.isclose(
            probability_sum,
            1.0,
            rel_tol=1e-9,
            abs_tol=1e-9,
        ):
            raise ValueError(
                f"Measurement probabilities are not normalized: "
                f"sum={probability_sum}"
            )

        # Ensure that every observed bitstring has an observable value.
        missing_states = [
            bitstring
            for bitstring in validated_counts
            if bitstring not in observable_values
        ]

        if missing_states:
            raise ValueError(
                "Observable values are missing for measured states: "
                f"{missing_states}"
            )

        validated_observables = {
            bitstring: self._validate_finite_number(
                observable_values[bitstring],
                f"observable value for {bitstring}",
            )
            for bitstring in validated_counts
        }

        # Equation 3: observable expectation.
        expectation = sum(
            probabilities[bitstring] * validated_observables[bitstring]
            for bitstring in validated_counts
        )

        # Equation 4: empirical observable variance.
        variance = sum(
            probabilities[bitstring]
            * (validated_observables[bitstring] - expectation) ** 2
            for bitstring in validated_counts
        )

        # Equation 5: standard error.
        standard_error = math.sqrt(variance / total_shots)

        # Equation 6: approximate confidence interval.
        confidence_interval = self._normal_confidence_interval(
            expectation,
            standard_error,
            confidence_level,
        )

        # Optional success probability.
        success_probability = None
        success_interval = None

        if success_states is not None:
            success_states_set = set(success_states)

            successful_shots = sum(
                count
                for bitstring, count in validated_counts.items()
                if bitstring in success_states_set
            )

            success_probability = successful_shots / total_shots

            success_interval = self._wilson_interval(
                successful_shots,
                total_shots,
                confidence_level,
            )

        # Optional application score.
        application_score = None

        if score_function is not None:
            application_score = sum(
                (validated_counts[bitstring] / total_shots)
                * self._validate_finite_number(
                    score_function(bitstring),
                    f"application score for {bitstring}",
                )
                for bitstring in validated_counts
            )

        # Equation 7: optional total variation distance.
        tvd = None

        if reference_distribution is not None:
            tvd = self.total_variation_distance(
                reference_distribution=reference_distribution,
                observed_distribution=probabilities,
            )

        quality_satisfied = self._check_quality_thresholds(
            standard_error=standard_error,
            success_probability=success_probability,
            application_score=application_score,
        )

        return QualityEstimate(
            sample_count=total_shots,
            expectation_value=expectation,
            variance=variance,
            standard_error=standard_error,
            confidence_interval=confidence_interval,
            success_probability=success_probability,
            application_score=application_score,
            quality_satisfied=quality_satisfied,
            metadata={
                "estimation_method": "measurement_counts",
                "confidence_level": confidence_level,
                "confidence_interval_method": "normal_approximation",
                "variance_method": "empirical_population_variance",
                "measurement_probabilities": probabilities,
                "probability_sum": probability_sum,
                "probability_normalized": True,
                "success_probability_interval": success_interval,
                "total_variation_distance": tvd,
                "reference_distribution_available": (
                    reference_distribution is not None
                ),
                "thresholds": self._threshold_metadata(),
            },
        )

    # ---------------------------------------------------------
    # Public method 3: Total variation distance (Equation 7)
    # ---------------------------------------------------------

    def total_variation_distance(
        self,
        reference_distribution: Mapping[str, float],
        observed_distribution: Mapping[str, float],
    ) -> float:
        """
        Calculate total variation distance between two distributions.

        Equation 7:

            TVD(P, Q) = 0.5 * sum_x |P(x) - Q(x)|

        Both distributions must be valid normalized probability
        distributions. Missing states are treated as having probability 0.
        """

        reference = self._validate_probability_distribution(
            reference_distribution,
            "reference_distribution",
        )

        observed = self._validate_probability_distribution(
            observed_distribution,
            "observed_distribution",
        )

        all_states = set(reference) | set(observed)

        tvd = 0.5 * sum(
            abs(
                reference.get(state, 0.0)
                - observed.get(state, 0.0)
            )
            for state in all_states
        )

        # Protect against tiny floating-point deviations.
        return min(1.0, max(0.0, tvd))

    # ---------------------------------------------------------
    # Validation helpers
    # ---------------------------------------------------------

    @staticmethod
    def _validate_counts(counts: Mapping[str, int]) -> Dict[str, int]:
        if not isinstance(counts, Mapping) or not counts:
            raise ValueError("counts must be a non-empty mapping.")

        validated = {}

        for bitstring, count in counts.items():
            if not isinstance(bitstring, str) or not bitstring:
                raise ValueError(
                    "Every measurement state must be a non-empty string."
                )

            if isinstance(count, bool) or not isinstance(count, int):
                raise ValueError(
                    f"Shot count for state {bitstring!r} must be an integer."
                )

            if count < 0:
                raise ValueError(
                    f"Shot count for state {bitstring!r} cannot be negative."
                )

            validated[bitstring] = count

        if sum(validated.values()) <= 0:
            raise ValueError("Total measurement shots must be greater than zero.")

        return validated

    @staticmethod
    def _validate_numeric_samples(
        samples: Sequence[float],
    ) -> list[float]:
        if (
            not isinstance(samples, Sequence)
            or isinstance(samples, (str, bytes))
            or len(samples) == 0
        ):
            raise ValueError("samples must be a non-empty numeric sequence.")

        return [
            QualityProfiler._validate_finite_number(
                value,
                "sample",
            )
            for value in samples
        ]

    @staticmethod
    def _validate_finite_number(value: Any, name: str) -> float:
        if isinstance(value, bool):
            raise ValueError(f"{name} must be a finite number.")

        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be a finite number.") from exc

        if not math.isfinite(number):
            raise ValueError(f"{name} must be a finite number.")

        return number

    @staticmethod
    def _validate_confidence_level(confidence_level: float) -> None:
        if (
            isinstance(confidence_level, bool)
            or not isinstance(confidence_level, (int, float))
            or not math.isfinite(confidence_level)
            or not 0.0 < confidence_level < 1.0
        ):
            raise ValueError(
                "confidence_level must be between 0 and 1, exclusive."
            )

    @staticmethod
    def _validate_probability_distribution(
        distribution: Mapping[str, float],
        name: str,
    ) -> Dict[str, float]:
        if not isinstance(distribution, Mapping) or not distribution:
            raise ValueError(f"{name} must be a non-empty mapping.")

        validated = {}

        for state, probability in distribution.items():
            if not isinstance(state, str) or not state:
                raise ValueError(
                    f"Every state in {name} must be a non-empty string."
                )

            probability = QualityProfiler._validate_finite_number(
                probability,
                f"probability for {state}",
            )

            if not 0.0 <= probability <= 1.0:
                raise ValueError(
                    f"Probability for state {state!r} must be between 0 and 1."
                )

            validated[state] = probability

        probability_sum = sum(validated.values())

        if not math.isclose(
            probability_sum,
            1.0,
            rel_tol=1e-9,
            abs_tol=1e-9,
        ):
            raise ValueError(
                f"{name} must be normalized; probabilities sum to "
                f"{probability_sum}."
            )

        return validated

    @staticmethod
    def _validate_optional_nonnegative(
        value: Optional[float],
        name: str,
    ) -> Optional[float]:
        if value is None:
            return None

        number = QualityProfiler._validate_finite_number(value, name)

        if number < 0:
            raise ValueError(f"{name} cannot be negative.")

        return number

    @staticmethod
    def _validate_optional_probability(
        value: Optional[float],
        name: str,
    ) -> Optional[float]:
        if value is None:
            return None

        number = QualityProfiler._validate_finite_number(value, name)

        if not 0.0 <= number <= 1.0:
            raise ValueError(f"{name} must be between 0 and 1.")

        return number

    # ---------------------------------------------------------
    # Statistical helpers
    # ---------------------------------------------------------

    @staticmethod
    def _normal_confidence_interval(
        mean: float,
        standard_error: float,
        confidence_level: float,
    ) -> Tuple[float, float]:
        alpha = 1.0 - confidence_level
        z_value = NormalDist().inv_cdf(1.0 - alpha / 2.0)

        margin = z_value * standard_error

        return (
            mean - margin,
            mean + margin,
        )

    @staticmethod
    def _wilson_interval(
        successes: int,
        total: int,
        confidence_level: float,
    ) -> Tuple[float, float]:
        """
        Wilson score interval for a binomial success probability.
        """

        if total <= 0:
            raise ValueError("total must be greater than zero.")

        alpha = 1.0 - confidence_level
        z = NormalDist().inv_cdf(1.0 - alpha / 2.0)

        p = successes / total
        z_squared = z**2

        denominator = 1.0 + z_squared / total

        center = (
            p + z_squared / (2.0 * total)
        ) / denominator

        margin = (
            z
            * math.sqrt(
                (p * (1.0 - p) / total)
                + (z_squared / (4.0 * total**2))
            )
            / denominator
        )

        return (
            max(0.0, center - margin),
            min(1.0, center + margin),
        )

    # ---------------------------------------------------------
    # Quality threshold evaluation
    # ---------------------------------------------------------

    def _check_quality_thresholds(
        self,
        standard_error: float,
        success_probability: Optional[float],
        application_score: Optional[float],
    ) -> Optional[bool]:
        """
        Check configured statistical and application-score thresholds.

        Returns:
            True  - all configured thresholds are satisfied.
            False - at least one configured threshold is not satisfied.
            None  - no thresholds have been configured.
        """

        checks = []

        if self.max_standard_error is not None:
            checks.append(
                standard_error <= self.max_standard_error
            )

        if self.min_success_probability is not None:
            if success_probability is None:
                raise ValueError(
                    "A success_predicate or success_states argument is "
                    "required when min_success_probability is configured."
                )

            checks.append(
                success_probability >= self.min_success_probability
            )

        if self.min_application_score is not None:
            if application_score is None:
                raise ValueError(
                    "A score_function is required when "
                    "min_application_score is configured."
                )

            checks.append(
                application_score >= self.min_application_score
            )

        if not checks:
            return None

        return all(checks)

    def _threshold_metadata(self) -> Dict[str, Optional[float]]:
        return {
            "max_standard_error": self.max_standard_error,
            "min_success_probability": self.min_success_probability,
            "min_application_score": self.min_application_score,
        }