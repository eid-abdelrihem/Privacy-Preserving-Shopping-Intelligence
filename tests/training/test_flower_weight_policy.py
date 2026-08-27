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
