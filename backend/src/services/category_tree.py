def build_path(parent_path: str | None, node_id: str) -> str:
    if not parent_path:
        return f"/{node_id}/"
    return f"{parent_path.rstrip('/')}/{node_id}/"


def assert_no_cycle(parent_path: str | None, node_id: str) -> None:
    if parent_path and f"/{node_id}/" in parent_path:
        raise ValueError("CYCLE_DETECTED")
