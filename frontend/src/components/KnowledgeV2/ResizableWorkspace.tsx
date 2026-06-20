import { Splitter } from "antd";
import type { ReactNode } from "react";
import { useCallback, useMemo, useState } from "react";

const STORAGE_KEY = "knowledge-v2-entry-layout";
const DEFAULT_OUTER: [number, number] = [20, 80];
const DEFAULT_INNER: [number, number] = [56.25, 43.75];

interface StoredLayout {
  outer: [number, number];
  inner: [number, number];
}

function readStoredLayout(): StoredLayout {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { outer: DEFAULT_OUTER, inner: DEFAULT_INNER };
    const parsed = JSON.parse(raw) as StoredLayout;
    if (!Array.isArray(parsed.outer) || !Array.isArray(parsed.inner)) {
      return { outer: DEFAULT_OUTER, inner: DEFAULT_INNER };
    }
    return {
      outer: [Number(parsed.outer[0]) || DEFAULT_OUTER[0], Number(parsed.outer[1]) || DEFAULT_OUTER[1]],
      inner: [Number(parsed.inner[0]) || DEFAULT_INNER[0], Number(parsed.inner[1]) || DEFAULT_INNER[1]],
    };
  } catch {
    return { outer: DEFAULT_OUTER, inner: DEFAULT_INNER };
  }
}

interface ResizableWorkspaceProps {
  treePanel: ReactNode;
  previewPanel: ReactNode;
  entryPanel: ReactNode;
}

export default function ResizableWorkspace({ treePanel, previewPanel, entryPanel }: ResizableWorkspaceProps) {
  const initial = useMemo(() => readStoredLayout(), []);
  const [outerSizes, setOuterSizes] = useState<[number, number]>(initial.outer);
  const [innerSizes, setInnerSizes] = useState<[number, number]>(initial.inner);

  const persistLayout = useCallback((outer: [number, number], inner: [number, number]) => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ outer, inner }));
    } catch {
      // ignore storage failures
    }
  }, []);

  return (
    <Splitter
      style={{ width: "100%", minHeight: "calc(100vh - 280px)" }}
      onResizeEnd={(sizes) => {
        const next: [number, number] = [Number(sizes[0]), Number(sizes[1])];
        setOuterSizes(next);
        persistLayout(next, innerSizes);
      }}
    >
      <Splitter.Panel size={`${outerSizes[0]}%`} min="200px">
        {treePanel}
      </Splitter.Panel>
      <Splitter.Panel size={`${outerSizes[1]}%`} min="200px">
        <Splitter
          onResizeEnd={(sizes) => {
            const next: [number, number] = [Number(sizes[0]), Number(sizes[1])];
            setInnerSizes(next);
            persistLayout(outerSizes, next);
          }}
        >
          <Splitter.Panel size={`${innerSizes[0]}%`} min="200px">
            {previewPanel}
          </Splitter.Panel>
          <Splitter.Panel size={`${innerSizes[1]}%`} min="200px">
            {entryPanel}
          </Splitter.Panel>
        </Splitter>
      </Splitter.Panel>
    </Splitter>
  );
}
