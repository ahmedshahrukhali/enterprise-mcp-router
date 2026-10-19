from src.router import EnterpriseMCPRouter, MCPToolSpec


def test_mcp_routing_and_governance():
    tools = [
        MCPToolSpec("read_ledger", "Read SQL accounting ledger", False, "analyst", [0.9, 0.1]),
        MCPToolSpec("execute_wire", "Execute outbound bank wire", True, "admin", [0.1, 0.9]),
    ]
    router = EnterpriseMCPRouter(tools)

    top = router.route_top_k_tools([0.85, 0.15], k=1)
    assert top == ["read_ledger"]

    # Mutating tool requires HITL approval
    res_pending = router.authorize_execution("execute_wire", ["admin"], hitl_approved=False)
    assert res_pending["allowed"] is False
    assert res_pending["reason"] == "hitl_approval_required"

    res_ok = router.authorize_execution("execute_wire", ["admin"], hitl_approved=True)
    assert res_ok["allowed"] is True
