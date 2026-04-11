"""Composable prompt block recipes for workflow-generated prompt templates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

DEFAULT_OUTPUT_FIELDS_TEMPLATE = "Return JSON object with required fields: ${required_json_fields_csv}."

BLOCK_ORDER = ("goal", "context_rules", "output_contract", "policy", "examples")
REQUIRED_BLOCK_TYPES = ("goal", "context_rules", "output_contract", "policy")


@dataclass(frozen=True)
class PromptBlock:
    block_type: str
    content: str


@dataclass(frozen=True)
class PromptBlockPack:
    workflow_type: str
    blocks: tuple[PromptBlock, ...]


DEFAULT_BLOCK_PACKS: dict[str, PromptBlockPack] = {
    "follow-up": PromptBlockPack(
        workflow_type="follow-up",
        blocks=(
            PromptBlock("goal", "Complete the ${stage_name} stage for the active follow-up workflow contract."),
            PromptBlock(
                "context_rules",
                "Return strict JSON only; include concise reasoning; confidence in [0,1].",
            ),
            PromptBlock("output_contract", DEFAULT_OUTPUT_FIELDS_TEMPLATE),
            PromptBlock(
                "policy",
                "Do not fabricate facts; confidence between 0 and 1; must not include unsupported claims.",
            ),
            PromptBlock(
                "examples",
                "Example pattern: if confidence < 0.6 then set escalation_required=true with concise rationale.",
            ),
        ),
    ),
    "outreach": PromptBlockPack(
        workflow_type="outreach",
        blocks=(
            PromptBlock("goal", "Complete the ${stage_name} stage for outreach generation and sequencing."),
            PromptBlock(
                "context_rules",
                "Return strict JSON only; include concise reasoning; confidence in [0,1].",
            ),
            PromptBlock("output_contract", DEFAULT_OUTPUT_FIELDS_TEMPLATE),
            PromptBlock(
                "policy",
                "Use respectful, non-coercive language and only claims grounded in provided CRM/context data.",
            ),
            PromptBlock(
                "examples",
                "Example pattern: use specific next-step ask with one concrete timeline option.",
            ),
        ),
    ),
    "intervention": PromptBlockPack(
        workflow_type="intervention",
        blocks=(
            PromptBlock("goal", "Complete the ${stage_name} stage for risk intervention handling."),
            PromptBlock(
                "context_rules",
                "Return strict JSON only; include concise reasoning; confidence in [0,1].",
            ),
            PromptBlock("output_contract", DEFAULT_OUTPUT_FIELDS_TEMPLATE),
            PromptBlock(
                "policy",
                "Avoid pressure tactics; identify uncertainty clearly; escalate policy-uncertain responses.",
            ),
            PromptBlock(
                "examples",
                "Example pattern: when high-risk ambiguity exists, recommend human_review_required=true.",
            ),
        ),
    ),
}


def canonical_workflow_type(value: str) -> str:
    normalized = value.strip().lower().replace("_", "-")
    aliases = {
        "followup": "follow-up",
        "deal-followup": "follow-up",
        "deal_followup": "follow-up",
        "new-deal-outreach": "outreach",
    }
    return aliases.get(normalized, normalized)


def validate_prompt_blocks(blocks: tuple[PromptBlock, ...]) -> None:
    if not blocks:
        raise ValueError("Prompt recipe must include at least one block.")

    seen: dict[str, int] = {}
    for block in blocks:
        if block.block_type not in BLOCK_ORDER:
            raise ValueError(f"Unknown prompt block type: {block.block_type}")
        if not block.content.strip():
            raise ValueError(f"Prompt block '{block.block_type}' cannot be empty.")
        seen[block.block_type] = seen.get(block.block_type, 0) + 1

    missing = [block_type for block_type in REQUIRED_BLOCK_TYPES if seen.get(block_type, 0) == 0]
    if missing:
        raise ValueError(f"Prompt recipe missing required blocks: {', '.join(missing)}")

    duplicates = [block_type for block_type, count in seen.items() if count > 1 and block_type in REQUIRED_BLOCK_TYPES]
    if duplicates:
        raise ValueError(f"Prompt recipe contains duplicate required blocks: {', '.join(sorted(duplicates))}")


def block_pack_for_workflow_type(workflow_type: str) -> PromptBlockPack:
    canonical = canonical_workflow_type(workflow_type)
    pack = DEFAULT_BLOCK_PACKS.get(canonical)
    if pack is None:
        known = ", ".join(sorted(DEFAULT_BLOCK_PACKS.keys()))
        raise ValueError(f"Unknown workflow_type '{workflow_type}'. Supported workflow types: {known}")
    validate_prompt_blocks(pack.blocks)
    return pack


def merge_prompt_blocks(
    *,
    default_blocks: tuple[PromptBlock, ...],
    overrides: Mapping[str, str] | None = None,
    extra_examples: tuple[str, ...] | None = None,
) -> tuple[PromptBlock, ...]:
    override_values = {key: value for key, value in (overrides or {}).items() if value is not None}
    unknown_override_keys = sorted(set(override_values.keys()) - set(BLOCK_ORDER))
    if unknown_override_keys:
        raise ValueError(f"Unknown prompt block override keys: {', '.join(unknown_override_keys)}")
    merged: list[PromptBlock] = []
    for block in default_blocks:
        content = override_values.get(block.block_type, block.content)
        merged.append(PromptBlock(block_type=block.block_type, content=content))

    if extra_examples:
        merged.extend(PromptBlock(block_type="examples", content=entry) for entry in extra_examples if entry.strip())

    merged_blocks = tuple(merged)
    validate_prompt_blocks(merged_blocks)
    return merged_blocks


def compose_template_from_blocks(*, role: str, blocks: tuple[PromptBlock, ...]) -> str:
    validate_prompt_blocks(blocks)
    grouped: dict[str, list[str]] = {kind: [] for kind in BLOCK_ORDER}
    for block in blocks:
        grouped[block.block_type].append(block.content.strip())

    task = grouped["goal"][0]
    constraints = grouped["context_rules"][0]
    output_fields = grouped["output_contract"][0]
    safety_limits = grouped["policy"][0]
    example_lines = grouped["examples"]
    examples_suffix = (
        " " + " ".join(f"{idx + 1}) {line}" for idx, line in enumerate(example_lines)) if example_lines else ""
    )

    return "\n".join(
        [
            "schema_version: v1",
            f"Role: You are {role}.",
            f"Task: {task}",
            f"Constraints: {constraints}",
            f"Output Fields: {output_fields}",
            f"Safety Limits: {safety_limits}",
            "Tone Policy: Keep tone professional, respectful, and non-coercive; avoid urgency inflation or emotional pressure.",
            "Legal/Compliance Boundaries: Do not provide legal, regulatory, or financial advice; do not claim legal compliance status without verified evidence.",
            "Allowed Claims: Only include claims grounded in provided context, approved CRM facts, or explicit workflow memory; mark unknowns as unknown.",
            "Policy Validators: Before finalizing output, check for unsupported claims, prohibited certainty language, and unresolved uncertainty markers.",
            "Escalation Instructions: If confidence < 0.6 or any high-risk/policy-uncertain content is present, flag escalation_required=true with concise rationale for human review.",
            f"Examples: Use as guidance only.{examples_suffix}",
        ]
    )
