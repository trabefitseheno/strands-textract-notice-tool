"""BEFORE: a Strands agent on Bedrock that rewrites notice TEXT in plain language. No tools."""

import sys

from strands import Agent

from agent.common import SYSTEM_PROMPT, model


def build() -> Agent:
    return Agent(model=model(), system_prompt=SYSTEM_PROMPT, callback_handler=None)


if __name__ == "__main__":
    print(build()(" ".join(sys.argv[1:])))
