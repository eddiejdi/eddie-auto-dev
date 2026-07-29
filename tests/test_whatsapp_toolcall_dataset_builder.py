"""Testes do dataset builder de tool-calling — paridade de schema com a
bridge (mesma fonte de verdade) e shape/volume básico do dataset gerado."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parent.parent / "scripts" / "whatsapp_toolcall_dataset_builder.py"


def _load_builder():
    module_name = "whatsapp_toolcall_dataset_builder_for_tests"
    cached = sys.modules.get(module_name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_template_generator_covers_every_visible_tool():
    builder = _load_builder()
    schemas = {s["function"]["name"]: s["function"] for s in builder.mcp_tool_bridge.build_ollama_tool_schemas()}
    for tool_name, fn in schemas.items():
        out = builder.template_generator(tool_name, fn.get("parameters", {}), 3)
        assert len(out) == 3
        for text, args in out:
            assert isinstance(text, str) and text
            assert isinstance(args, dict)
            required = set(fn.get("parameters", {}).get("required", []) or [])
            assert required.issubset(args.keys())


def test_build_dataset_shape_and_volume():
    builder = _load_builder()
    examples = builder.build_dataset("template", per_tool=5, ollama_host="", ollama_model="")

    assert len(examples) > 0
    positives = [e for e in examples if e["tool_calls"]]
    negatives = [e for e in examples if not e["tool_calls"]]

    # todo positivo referencia uma ferramenta que existe de verdade
    visible = builder.mcp_tool_bridge.discovered_tool_names(include_excluded=False)
    for ex in positives:
        name = ex["tool_calls"][0]["function"]["name"]
        assert name in visible

    # negativos devem ser uma fração substancial (guarda contra over-triggering)
    assert len(negatives) >= len(positives) * 0.2

    for ex in examples:
        assert "instruction" in ex and ex["instruction"]
        assert "tool_calls" in ex


def test_second_turn_examples_only_cover_declared_subset():
    builder = _load_builder()
    import random

    examples = builder._second_turn_examples(3, random.Random(0))
    names = {e["tool_calls"][0]["function"]["name"] for e in examples}
    assert names.issubset(set(builder.SECOND_TURN_TOOLS))
    for ex in examples:
        assert "tool_result" in ex
        assert ex["output"]


def test_negative_and_near_miss_examples_never_carry_tool_calls():
    builder = _load_builder()
    for ex in builder._negative_examples() + builder._near_miss_examples():
        assert ex["tool_calls"] == []
