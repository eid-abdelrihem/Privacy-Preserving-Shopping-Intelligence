from __future__ import annotations

import importlib

import ray
import torch
from flwr.app import ArrayRecord

from ppsi.training.centralized import CentralizedAdapter
from ppsi.training.core import LocalTrainerCore
from ppsi.training.fixtures import (
    default_batch_spec,
    make_phase1_batch,
    make_stub_model,
)
from ppsi.training.flower import (
    ContributingRowsSmokeWeightPolicy,
    FlowerLocalAdapter,
)
from ppsi.training.objective import ContractSmokeObjective
from ppsi.training.sampler import TrainingCursor
from ppsi.training.state import load_shared_state, pack_shared_state
from scripts.training_smoke import execute


def _core(model):
    optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=1, gamma=0.9)
    return LocalTrainerCore(
        model=model,
        batch_spec=default_batch_spec(),
        objective=ContractSmokeObjective(),
        optimizer=optimizer,
        scheduler=scheduler,
        device="cpu",
    )


def test_reusable_training_module_imports_in_real_ray_worker():
    ray.init(num_cpus=1, include_dashboard=False, ignore_reinit_error=True)

    @ray.remote
    def worker_import():
        module = importlib.import_module("ppsi.training")
        return module.Phase1Batch.__name__

    try:
        assert ray.get(worker_import.remote()) == "Phase1Batch"
    finally:
        ray.shutdown()


def test_arrayrecord_round_trip_preserves_centralized_flower_step_parity():
    batch = make_phase1_batch()
    source = make_stub_model(seed=13)
    initial = pack_shared_state(source, source.shared_state_spec())
    array_record = ArrayRecord.from_torch_state_dict(initial)
    transported = array_record.to_torch_state_dict()

    centralized_model = make_stub_model(seed=42)
    load_shared_state(
        centralized_model,
        transported,
        centralized_model.shared_state_spec(),
    )
    centralized_core = _core(centralized_model)
    centralized_summary = CentralizedAdapter(centralized_core).train_batches(
        [batch],
        cursor=TrainingCursor(None, 0, 0, 0),
    )
    centralized_state = pack_shared_state(
        centralized_model,
        centralized_model.shared_state_spec(),
    )

    flower_model = make_stub_model(seed=2026)
    flower_core = _core(flower_model)
    flower_result = FlowerLocalAdapter(
        flower_core,
        flower_model.shared_state_spec(),
        ContributingRowsSmokeWeightPolicy(),
    ).fit(transported, [batch], outer_round=1)

    assert centralized_summary.contributing_examples == flower_result.aggregation_weight
    for task, stat in centralized_summary.task_stats.items():
        other = flower_result.summary.task_stats[task]
        assert stat == other
    for key, value in centralized_state.items():
        torch.testing.assert_close(
            value,
            flower_result.shared_state[key],
            rtol=0,
            atol=0,
        )


def test_unified_trainer_runs_through_real_flower_three_round_lifecycle():
    summary = execute(
        {
            "schema": "unified_trainer_smoke_v1",
            "version": "1",
            "seed": 13,
            "num_clients": 2,
            "num_rounds": 3,
            "repeat_runs": 2,
            "learning_rate": 0.01,
            "tolerance": 1e-6,
        }
    )
    assert summary["status"] == "PASS"
    assert len(summary["repetitions"]) == 2
    assert (
        summary["repetitions"][0]["final_model_digest"]
        == summary["repetitions"][1]["final_model_digest"]
    )
