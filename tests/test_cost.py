from types import SimpleNamespace

from safe_change_agent.cost import CostAccumulator, cost_usd


def test_cost_usd_known_model():
    # 1M input + 1M output on gpt-4.1-mini = 0.40 + 1.60
    assert cost_usd("openai:gpt-4.1-mini", 1_000_000, 1_000_000) == 2.0


def test_cost_usd_unknown_model_is_free():
    assert cost_usd("openai:made-up", 1000, 1000) == 0.0


def test_accumulator_sums_runs():
    acc = CostAccumulator(model="openai:gpt-4.1-mini")
    acc.add(SimpleNamespace(input_tokens=1000, output_tokens=100))
    acc.add(SimpleNamespace(input_tokens=2000, output_tokens=200))
    assert (acc.runs, acc.input_tokens, acc.output_tokens) == (2, 3000, 300)
    assert round(acc.total_cost, 6) == round((3000 * 0.40 + 300 * 1.60) / 1_000_000, 6)
