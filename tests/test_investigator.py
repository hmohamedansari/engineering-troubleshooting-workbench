import pytest

from workbench.investigator import investigate, load_scenario, transition_state


def test_recent_deployment_with_high_errors_uses_regression_route() -> None:
    report = investigate(load_scenario("checkout-regression"))

    assert report.route == "possible-deployment-regression"
    assert report.next_step.startswith("Ask an engineer")
    assert any(event.kind == "evidence.collected" for event in report.events)
    assert any(finding.label == "Payment provider error rate" for finding in report.findings)
    assert all(hypothesis.status == "unproven" for hypothesis in report.hypotheses)


def test_normal_checkout_stays_on_observation_route() -> None:
    report = investigate(load_scenario("normal-checkout"))

    assert report.route == "normal-observation"
    assert report.state == "triaged"


def test_old_deployment_with_high_errors_uses_degradation_route() -> None:
    scenario = load_scenario("checkout-regression")
    scenario["deployment"]["minutes_ago"] = 120

    report = investigate(scenario)

    assert report.route == "checkout-service-degradation"


def test_disproved_hypothesis_stays_visible_as_a_dead_end() -> None:
    report = investigate(
        load_scenario("checkout-regression"),
        {"payment-provider-failure": "disproved"},
    )

    payment_hypothesis = next(item for item in report.hypotheses if item.id == "payment-provider-failure")
    assert payment_hypothesis.status == "disproved"
    assert "0.0%" in payment_hypothesis.disproof_evidence
    assert any(event.kind == "hypothesis.disproved" for event in report.events)


def test_hypothesis_without_evidence_cannot_be_marked_disproved() -> None:
    with pytest.raises(ValueError, match="without evidence"):
        investigate(
            load_scenario("checkout-regression"),
            {"deployment-validation-change": "disproved"},
        )


def test_state_transitions_are_explicit_and_reject_invalid_moves() -> None:
    assert transition_state("triaged", "investigating") == "investigating"

    with pytest.raises(ValueError, match="Cannot move"):
        transition_state("triaged", "resolved")


def test_delayed_metric_records_a_visible_bounded_retry() -> None:
    report = investigate(load_scenario("delayed-metric"))

    kinds = [event.kind for event in report.events]
    assert "metric.snapshot.retry-scheduled" in kinds
    assert "workflow.completed" in kinds


def test_duplicate_alert_is_suppressed_with_an_idempotency_key() -> None:
    report = investigate(load_scenario("duplicate-alert"))

    duplicate_event = next(event for event in report.events if event.kind == "alert.duplicate-suppressed")
    assert "1 duplicate" in duplicate_event.message
    assert "idempotency_key" not in duplicate_event.message
    assert "alert:checkout-5xx" in duplicate_event.message
