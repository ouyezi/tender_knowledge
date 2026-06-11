export interface TreeNodeWithId {
  id: string;
  label: string;
  children: TreeNodeWithId[];
}

export function flattenTreeOptions(
  nodes: Array<{ id: string; label: string; children: TreeNodeWithId["children"] }>,
  prefix = "",
): Array<{ label: string; value: string }> {
  const result: Array<{ label: string; value: string }> = [];
  for (const node of nodes) {
    const label = prefix ? `${prefix} / ${node.label}` : node.label;
    result.push({ label, value: node.id });
    result.push(...flattenTreeOptions(node.children, label));
  }
  return result;
}

export function collectDescendantIds(
  nodes: Array<{ id: string; children: TreeNodeWithId["children"] }>,
  rootId: string,
): Set<string> {
  const ids = new Set<string>();

  const walk = (node: { id: string; children: TreeNodeWithId["children"] }) => {
    ids.add(node.id);
    node.children.forEach(walk);
  };

  const find = (
    list: Array<{ id: string; children: TreeNodeWithId["children"] }>,
  ): boolean => {
    for (const node of list) {
      if (node.id === rootId) {
        walk(node);
        return true;
      }
      if (find(node.children)) {
        return true;
      }
    }
    return false;
  };

  find(nodes);
  return ids;
}
