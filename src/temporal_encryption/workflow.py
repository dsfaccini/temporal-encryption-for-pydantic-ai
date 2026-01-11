from decimal import Decimal

from pydantic_ai.durable_exec.temporal import PydanticAIWorkflow
from temporalio import workflow

from .agent import TradeDecision, TradingDeps, temporal_agent


@workflow.defn
class TradingWorkflow(PydanticAIWorkflow):
    """Workflow that runs the trading agent with encrypted state.

    All trading data (positions, API keys, decisions) is encrypted
    before reaching the Temporal server.
    """

    __pydantic_ai_agents__ = [temporal_agent]

    @workflow.run
    async def run(
        self,
        prompt: str,
        trader_id: str,
        api_key: str,
        max_position_size: str,
    ) -> TradeDecision:
        deps = TradingDeps(
            trader_id=trader_id,
            api_key=api_key,
            max_position_size=Decimal(max_position_size),
        )
        result = await temporal_agent.run(prompt, deps=deps)
        return result.output
