"""AFTER: the same agent plus ONE new tool, read_notice_document (Amazon Textract)."""

import sys

from strands import Agent

from agent.common import SYSTEM_PROMPT, model
from tools.read_notice_document import read_notice_document


def build() -> Agent:
    return Agent(
        model=model(),
        system_prompt=SYSTEM_PROMPT,
        tools=[read_notice_document],  # <- the whole integration
        callback_handler=None,
    )


if __name__ == "__main__":
    print(build()(" ".join(sys.argv[1:])))
