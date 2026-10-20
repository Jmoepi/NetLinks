"""Amazon Bedrock provider: Claude via converse() for extraction/RFQ, Titan v2 for embeddings."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from app.ai import prompts
from app.config import get_settings

_AWS_ENV_VARS = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_PROFILE")


def _clean_aws_env() -> None:
    """Compose passes unset AWS_* vars as empty strings; boto3 would treat AWS_PROFILE='' as a profile."""
    for var in _AWS_ENV_VARS:
        if os.environ.get(var) == "":
            del os.environ[var]
    # Local/ECS runs never need EC2 instance metadata; skipping it avoids slow credential probes.
    os.environ.setdefault("AWS_EC2_METADATA_DISABLED", "true")


def parse_json_object(text: str) -> dict[str, Any]:
    """Parse the first JSON object in a model reply, tolerating markdown fences."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("Model reply did not contain a JSON object")
    result = json.loads(cleaned[start : end + 1])
    if not isinstance(result, dict):
        raise ValueError("Model reply JSON is not an object")
    return result


class BedrockProvider:
    name = "bedrock"
    generated_by = "bedrock"

    def __init__(self) -> None:
        _clean_aws_env()
        settings = get_settings()
        self.region = settings.bedrock_region
        self.extraction_model_id = settings.bedrock_extraction_model_id
        self.embedding_model_id = settings.bedrock_embedding_model_id
        self._client: Any = None

    def _session(self) -> Any:
        import boto3

        return boto3.Session(region_name=self.region)

    def available(self) -> bool:
        if not self.extraction_model_id or not self.embedding_model_id:
            return False
        try:
            return self._session().get_credentials() is not None
        except Exception:  # noqa: BLE001  (any credential-chain error means "not available")
            return False

    def _runtime(self) -> Any:
        if self._client is None:
            from botocore.config import Config

            self._client = self._session().client(
                "bedrock-runtime",
                config=Config(read_timeout=120, retries={"max_attempts": 3, "mode": "standard"}),
            )
        return self._client

    def _converse_json(self, system: str, user: str) -> dict[str, Any]:
        resp = self._runtime().converse(
            modelId=self.extraction_model_id,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": user}]}],
            inferenceConfig={"maxTokens": 4096, "temperature": 0},
        )
        blocks = resp["output"]["message"]["content"]
        return parse_json_object("".join(b.get("text", "") for b in blocks))

    def extract_document(self, pages: list[str], filename: str) -> dict[str, Any]:
        return self._converse_json(
            prompts.EXTRACTION_SYSTEM_PROMPT, prompts.extraction_user_prompt(pages, filename)
        )

    def structure_rfq(self, text: str) -> dict[str, Any]:
        return self._converse_json(prompts.RFQ_SYSTEM_PROMPT, prompts.rfq_user_prompt(text))

    def embed(self, text: str) -> list[float]:
        resp = self._runtime().invoke_model(
            modelId=self.embedding_model_id,
            body=json.dumps({"inputText": text}),
            contentType="application/json",
            accept="application/json",
        )
        payload = json.loads(resp["body"].read())
        return [float(v) for v in payload["embedding"]]
