import asyncio
import dataclasses
import os
import uuid

import temporalio.converter
from dotenv import load_dotenv
from pydantic_ai.durable_exec.temporal import PydanticAIPlugin
from temporalio.client import Client

from .codec import load_encryption_codec
from .workflow import TradingWorkflow

TASK_QUEUE = 'encrypted-trading-queue'


async def main():
    load_dotenv()

    encryption_codec = load_encryption_codec()
    data_converter = dataclasses.replace(
        temporalio.converter.default(),
        payload_codec=encryption_codec,
    )

    client = await Client.connect(
        os.environ.get('TEMPORAL_HOST', 'localhost:7233'),
        data_converter=data_converter,
        plugins=[PydanticAIPlugin()],
    )

    workflow_id = f'trading-{uuid.uuid4()}'

    # Example: Analyze BTC market and decide on a trade
    result = await client.execute_workflow(
        TradingWorkflow.run,
        args=[
            'Analyze the btc-100k-2025 market. Should I buy more YES shares given my current position?',
            'trader-001',
            'market_api_key_xxxxx',  # This sensitive data is encrypted!
            '1000',
        ],
        id=workflow_id,
        task_queue=TASK_QUEUE,
    )

    print(f'Workflow {workflow_id} completed')
    print(f'Decision: {result.action.upper()} {result.market_id}')
    print(f'Amount: ${result.amount}')
    print(f'Confidence: {result.confidence:.0%}')
    print(f'Reasoning: {result.reasoning}')


if __name__ == '__main__':
    asyncio.run(main())
