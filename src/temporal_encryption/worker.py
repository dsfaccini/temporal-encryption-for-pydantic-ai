import asyncio
import dataclasses
import os

import temporalio.converter
from dotenv import load_dotenv
from pydantic_ai.durable_exec.temporal import PydanticAIPlugin
from temporalio.client import Client
from temporalio.worker import Worker

from .codec import load_encryption_codec
from .workflow import TradingWorkflow

TASK_QUEUE = 'encrypted-trading-queue'


async def run_worker():
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

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[TradingWorkflow],
    ):
        print(f'Worker started on task queue: {TASK_QUEUE}')
        print('All payloads are encrypted with AES-256-GCM')
        print('Sensitive data (API keys, positions, trades) never visible to Temporal server')
        await asyncio.Event().wait()


if __name__ == '__main__':
    asyncio.run(run_worker())
