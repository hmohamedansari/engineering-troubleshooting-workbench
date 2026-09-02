from workbench.investigator import investigate, load_scenario


def test_recent_deployment_with_high_errors_uses_regression_route() -> None:
    report = investigate(load_scenario("checkout-regression"))

    assert report.route == "possible-deployment-regression"
    assert report.next_step.startswith("Ask an engineer")
    assert any(event.kind == "evidence.collected" for event in report.events)


def test_normal_checkout_stays_on_observation_route() -> None:
    report = investigate(load_scenario("normal-checkout"))

    assert report.route == "normal-observation"
    assert report.state == "triaged"


def test_old_deployment_with_high_errors_uses_degradation_route() -> None:
    scenario = load_scenario("checkout-regression")
    scenario["deployment"]["minutes_ago"] = 120

    report = investigate(scenario)

    assert report.route == "checkout-service-degradation"
