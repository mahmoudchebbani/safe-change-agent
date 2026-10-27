from dataclasses import dataclass

# USD per 1M tokens
MODEL_PRICES = {
    "openai:gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "openai:gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "openai:gpt-5-mini": {"input": 0.25, "output": 2.00},
    "bedrock:us.anthropic.claude-sonnet-4-5-20250929-v1:0": {"input": 3.00, "output": 15.00},
}


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    prices = MODEL_PRICES.get(model.lower(), {"input": 0.0, "output": 0.0})
    return (input_tokens / 1_000_000) * prices["input"] + \
           (output_tokens / 1_000_000) * prices["output"]


@dataclass
class CostAccumulator:
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    runs: int = 0

    def add(self, usage) -> None:
        self.input_tokens += usage.input_tokens or 0
        self.output_tokens += usage.output_tokens or 0
        self.runs += 1

    @property
    def total_cost(self) -> float:
        return cost_usd(self.model, self.input_tokens, self.output_tokens)
