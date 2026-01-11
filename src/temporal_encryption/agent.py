from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.durable_exec.temporal import TemporalAgent


@dataclass
class TradingDeps:
    trader_id: str
    api_key: str
    max_position_size: Decimal


class TradeDecision(BaseModel):
    action: Literal['buy', 'sell', 'hold']
    market_id: str
    amount: Decimal
    reasoning: str
    confidence: float


agent = Agent(
    'google-vertex:gemini-3-flash-preview',
    deps_type=TradingDeps,
    output_type=TradeDecision,
    name='trading_agent',
    instructions="""You are a trading agent for prediction markets.

Analyze market data and make trading decisions. Consider:
- Current market prices and liquidity
- Position limits and risk management
- Market sentiment and recent news

Always provide clear reasoning and a confidence score (0-1).
Be conservative - recommend "hold" if uncertain.""",
)


@agent.tool
async def get_trader_info(ctx: RunContext[TradingDeps]) -> str:
    """Get information about the current trader and their limits."""
    return f'Trader ID: {ctx.deps.trader_id}, Max position: ${ctx.deps.max_position_size}'


@agent.tool
async def get_market_data(ctx: RunContext[TradingDeps], market_id: str) -> str:
    """Fetch current market data for a prediction market.

    In production, this would call the Market API.
    """
    # Simulated market data - in production this calls Market API
    markets = {
        'btc-100k-2025': {
            'question': 'Will BTC reach $100k by end of 2025?',
            'yes_price': 0.72,
            'no_price': 0.28,
            'volume_24h': 150000,
            'liquidity': 500000,
        },
        'fed-rate-cut-q1': {
            'question': 'Will the Fed cut rates in Q1 2025?',
            'yes_price': 0.45,
            'no_price': 0.55,
            'volume_24h': 80000,
            'liquidity': 200000,
        },
    }

    if market_id not in markets:
        return f'Market {market_id} not found'

    m = markets[market_id]
    return (
        f'Market: {m["question"]}\n'
        f'YES: ${m["yes_price"]:.2f} | NO: ${m["no_price"]:.2f}\n'
        f'24h Volume: ${m["volume_24h"]:,} | Liquidity: ${m["liquidity"]:,}'
    )


@agent.tool
async def get_current_positions(ctx: RunContext[TradingDeps]) -> str:
    """Get the trader's current positions."""
    # Simulated positions - in production this queries the database
    return (
        f'Positions for {ctx.deps.trader_id}:\n'
        '- btc-100k-2025: 100 YES shares @ $0.65 avg\n'
        '- fed-rate-cut-q1: 50 NO shares @ $0.60 avg\n'
        'Total exposure: $165'
    )


temporal_agent = TemporalAgent(agent)
