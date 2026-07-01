export const PREFACE_NODE_ID = "__preface__";

export function isPrefaceNodeId(nodeId?: string | null): boolean {
  return nodeId === PREFACE_NODE_ID;
}
