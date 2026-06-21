import type { ReactNode } from "react";
import type { KnowledgeAssetLike } from "./buildContentBlocks";
import { toAbsoluteMediaUrl } from "./resolveKnowledgeImageUrl";

export function parseMarkdownTable(raw?: string | null): { headers: string[]; rows: string[][] } | null {
  if (!raw) return null;
  const lines = raw
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  if (lines.length < 2) return null;
  const separator = lines[1].replace(/\|/g, "").replace(/[-:\s]/g, "");
  if (separator.length > 0) return null;

  const parseLine = (line: string) =>
    line
      .replace(/^\|/, "")
      .replace(/\|$/, "")
      .split("|")
      .map((cell) => cell.trim());

  const headers = parseLine(lines[0]);
  if (headers.length === 0) return null;
  const rows = lines.slice(2).map(parseLine).filter((row) => row.length > 0);
  return { headers, rows };
}

export function renderKnowledgeAsset(asset: KnowledgeAssetLike): ReactNode {
  if (asset.asset_type === "image" && asset.image_storage_url) {
    return (
      <img
        src={toAbsoluteMediaUrl(asset.image_storage_url)}
        alt={asset.asset_code ?? `image-${asset.id}`}
        style={{ maxWidth: "100%", border: "1px solid #f0f0f0", borderRadius: 6 }}
      />
    );
  }
  if (asset.asset_type === "table") {
    const table = parseMarkdownTable(asset.raw_markdown);
    if (table) {
      return (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {table.headers.map((header) => (
                  <th
                    key={header}
                    style={{ border: "1px solid #f0f0f0", textAlign: "left", padding: 8, background: "#fafafa" }}
                  >
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row, index) => (
                <tr key={`r-${index}`}>
                  {row.map((cell, cellIndex) => (
                    <td key={`c-${index}-${cellIndex}`} style={{ border: "1px solid #f0f0f0", padding: 8 }}>
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }
  }
  return (
    <pre style={{ whiteSpace: "pre-wrap", margin: 0, background: "#fafafa", padding: 12, borderRadius: 6 }}>
      {asset.raw_markdown || "(无预览数据)"}
    </pre>
  );
}
