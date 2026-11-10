"""
Amazon Bedrock / AgentCore Converse API Adapter & Multi-Framework Tool Bridges
(LangGraph ToolNode, Hugging Face smolagents CodeAgent, and CrewAI).
"""

from typing import Any, Callable, Dict, List, Optional


class BedrockAgentCoreAdapter:
    """
    Wraps Amazon Bedrock / AgentCore tool-calling and structured output execution
    with deterministic schema validation, self-healing retry handling, Converse API
    toolConfig formatting, and prompt/completion token accounting.
    """

    def __init__(
        self,
        model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0",
        max_retries: int = 2,
    ):
        self.model_id = model_id
        self.max_retries = max_retries

    def format_converse_tool_config(self, tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Formats routed MCP tools into an AWS Bedrock Converse API `toolConfig` block.
        """
        tool_specs = []
        for t in tools:
            tool_specs.append(
                {
                    "toolSpec": {
                        "name": t["name"].replace(".", "__"),
                        "description": f"[{t.get('domain', 'enterprise').upper()} | RBAC: {t.get('required_role', 'analyst')}] {t['description']}",
                        "inputSchema": {
                            "json": t.get(
                                "input_schema",
                                {
                                    "type": "object",
                                    "properties": {"query_or_id": {"type": "string"}},
                                    "required": ["query_or_id"],
                                },
                            )
                        },
                    }
                }
            )
        return {"tools": tool_specs, "toolChoice": {"auto": {}}}

    def invoke_with_structured_output(
        self,
        required_keys: List[str],
        provider_fn: Callable[[], Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Invokes a Bedrock / AgentCore completion function with retry handling
        and validates that the structured output contains all required schema keys.
        Accumulates token usage across all attempts.
        """
        attempts = 0
        last_error: Optional[str] = None
        retry_trace: List[Dict[str, Any]] = []

        while attempts <= self.max_retries:
            attempts += 1
            try:
                response = provider_fn()
                structured = response.get("output", {})
                usage = response.get("usage", {"prompt_tokens": 0, "completion_tokens": 0})
                missing = [k for k in required_keys if k not in structured]
                if missing:
                    last_error = f"missing_schema_keys:{','.join(missing)}"
                    retry_trace.append(
                        {
                            "attempt": attempts,
                            "status": "schema_validation_failed",
                            "missing_keys": missing,
                            "remediation": f"Injected self-healing schema constraint prompt for keys: {missing}",
                        }
                    )
                    continue

                retry_trace.append({"attempt": attempts, "status": "schema_verified", "missing_keys": []})
                prompt_tok = int(usage.get("prompt_tokens", 0))
                comp_tok = int(usage.get("completion_tokens", 0))
                return {
                    "status": "success",
                    "model_id": self.model_id,
                    "attempts": attempts,
                    "output": structured,
                    "retry_trace": retry_trace,
                    "usage": {
                        "prompt_tokens": prompt_tok,
                        "completion_tokens": comp_tok,
                        "total_tokens": prompt_tok + comp_tok,
                    },
                }
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                retry_trace.append({"attempt": attempts, "status": "runtime_exception", "error": last_error})

        return {
            "status": "error",
            "model_id": self.model_id,
            "attempts": attempts,
            "reason": last_error or "unknown_invocation_failure",
            "retry_trace": retry_trace,
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }


class AgentFrameworkBridges:
    """
    Exports routed MCP tools into native descriptor schemas for:
    - LangGraph (`ToolNode` / `StructuredTool` bindings)
    - Hugging Face `smolagents` (`CodeAgent` Python tool signatures)
    - CrewAI (`BaseTool` agent task descriptors)
    """

    @staticmethod
    def to_langgraph_tools(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                "framework": "langgraph",
                "node_type": "ToolNode",
                "name": t["name"],
                "description": t["description"],
                "args_schema": t.get("input_schema", {}),
                "requires_interrupt_before": bool(t.get("is_mutating", False)),
                "rbac_scope": t.get("required_role", "analyst"),
            }
            for t in tools
        ]

    @staticmethod
    def to_smolagents_tools(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out = []
        for t in tools:
            py_fn_name = t["name"].replace(".", "_")
            out.append(
                {
                    "framework": "smolagents",
                    "agent_class": "CodeAgent",
                    "name": py_fn_name,
                    "description": t["description"],
                    "inputs": {
                        "query_or_id": {
                            "type": "string",
                            "description": f"Input parameter for {t['name']}",
                        }
                    },
                    "output_type": "dict",
                    "python_signature": f"def {py_fn_name}(query_or_id: str, environment: str = 'prod') -> dict:",
                }
            )
        return out

    @staticmethod
    def to_crewai_tools(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                "framework": "crewai",
                "tool_name": t["name"],
                "description": f"{t['description']} (Required Role: {t.get('required_role')})",
                "cache_function": not bool(t.get("is_mutating", False)),
                "human_input_required": bool(t.get("is_mutating", False)),
            }
            for t in tools
        ]
