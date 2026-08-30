from __future__ import annotations

import pytest
import torch

from ppsi.training.core import LocalTrainerCore
from ppsi.training.fixtures import default_batch_spec, make_phase1_batch, make_stub_model
from ppsi.training.flower import (
    ContributingRowsSmokeWeightPolicy,
    FlowerLocalAdapter,
)
from ppsi.training.objective import ContractSmokeObjective
from ppsi.training.state import pack_shared_state


def _core():
    model = make_stub_model()
    return LocalTrainerCore(
        model=model,
        batch_spec=default_batch_spec(),
        objective=ContractSmokeObjective(),
        optimizer=torch.optim.SGD(model.parameters(), lr=0.01),
        device="cpu",
    )


def _momentum_core():
    model = make_stub_model(seed=42)
    optimizer = torch.optim.SGD(model.parameters(), lr=0.01, momentum=0.9)
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=1, gamma=0.9)
    return LocalTrainerCore(
        model=model,
        batch_spec=default_batch_spec(),
        objective=ContractSmokeObjective(),
        optimizer=optimizer,
        scheduler=scheduler,
        device="cpu",
    )


class FixedWeightPolicy:
    policy_id = "fixed_test_weight_v1"

    def __init__(self, value):
        self.value = value

    def __call__(self, summary):
        return self.value


def test_smoke_weight_policy_is_explicit_and_uses_contributing_rows():
    core = _core()
    initial = pack_shared_state(core.model, core.shared_state_spec)
    result = FlowerLocalAdapter(
        core,
        core.shared_state_spec,
        ContributingRowsSmokeWeightPolicy(),
    ).fit(initial, [make_phase1_batch()], outer_round=1)
    assert result.aggregation_weight == result.summary.contributing_examples


def test_adapter_does_not_hardcode_scientific_weight_policy():
    core = _core()
    initial = pack_shared_state(core.model, core.shared_state_spec)
    result = FlowerLocalAdapter(
        core,
        core.shared_state_spec,
        FixedWeightPolicy(7),
    ).fit(initial, [make_phase1_batch()], outer_round=1)
    assert result.aggregation_weight == 7


@pytest.mark.parametrize("bad_weight", [-1, 1.5, True])
def test_invalid_weight_policy_output_fails(bad_weight):
    core = _core()
    initial = pack_shared_state(core.model, core.shared_state_spec)
    adapter = FlowerLocalAdapter(
        core,
        core.shared_state_spec,
        FixedWeightPolicy(bad_weight),
    )
    with pytest.raises((TypeError, ValueError), match="AggregationWeightPolicy"):
        adapter.fit(initial, [make_phase1_batch()], outer_round=1)


def test_optimizer_and_scheduler_reset_for_each_completed_server_round():
    source = make_stub_model(seed=13)
    incoming = pack_shared_state(source, source.shared_state_spec())
    batch = make_phase1_batch()

    reused_core = _momentum_core()
    reused = FlowerLocalAdapter(
        reused_core,
        reused_core.shared_state_spec,
        ContributingRowsSmokeWeightPolicy(),
    )
    reused.fit(incoming, [batch], outer_round=1)
    second_round = reused.fit(incoming, [batch], outer_round=2)

    fresh_core = _momentum_core()
    fresh = FlowerLocalAdapter(
        fresh_core,
        fresh_core.shared_state_spec,
        ContributingRowsSmokeWeightPolicy(),
    )
    fresh_round = fresh.fit(incoming, [batch], outer_round=2)

    assert reused.optimizer_lifecycle == "RESET_EACH_SERVER_ROUND"
    assert reused_core.optimizer_step_count == fresh_core.optimizer_step_count == 1
    assert second_round.shared_state.keys() == fresh_round.shared_state.keys()
    for key in second_round.shared_state:
        torch.testing.assert_close(
            second_round.shared_state[key],
            fresh_round.shared_state[key],
            rtol=0,
            atol=0,
        )
