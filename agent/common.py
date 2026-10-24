"""Shared Bedrock model + system prompt for the baseline and with-tool agents."""

import os

from strands.models import BedrockModel

MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")
REGION = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"

SYSTEM_PROMPT = (
    "You help residents understand public notices. Given a notice, rewrite it in plain language "
    "(short sentences, about a 6th-grade reading level) and state who it applies to and any "
    "deadline. Copy every date, amount and place exactly. If you do not actually have the notice "
    "text, say so and ask for it; never invent notice content."
)


def model() -> BedrockModel:
    return BedrockModel(model_id=MODEL_ID, temperature=0.0, region_name=REGION)
