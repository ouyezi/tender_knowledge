export interface ImageExtractionFields {
  image_caption?: string | null;
  image_ocr_text?: string | null;
  extracted_facts?: Record<string, unknown> | null;
  llm_summary?: string | null;
}

export function hasImageExtraction(asset: ImageExtractionFields): boolean {
  return Boolean(
    asset.image_caption?.trim() ||
      asset.image_ocr_text?.trim() ||
      asset.llm_summary?.trim() ||
      (asset.extracted_facts && Object.keys(asset.extracted_facts).length > 0),
  );
}

export function getImageInformationRole(asset: ImageExtractionFields): "core" | "auxiliary" | null {
  const facts = asset.extracted_facts;
  if (!facts) {
    return null;
  }
  const role = facts.information_role ?? facts.role;
  if (role === "core" || role === "auxiliary") {
    return role;
  }
  return null;
}

/** 证书/资质等核心图片；无 role 时根据 OCR 或结构化事实推断。 */
export function isCoreImageAsset(asset: ImageExtractionFields): boolean {
  const role = getImageInformationRole(asset);
  if (role === "core") {
    return true;
  }
  if (role === "auxiliary") {
    return false;
  }
  const facts = asset.extracted_facts ?? {};
  if (facts.cert_name || facts.issue_date || facts.expire_date) {
    return true;
  }
  const ocr = asset.image_ocr_text?.trim() ?? "";
  if (ocr.length >= 8) {
    return true;
  }
  const caption = asset.image_caption?.trim() ?? "";
  return /证书|许可|资质|认证|备案|证明|执照|ISO|GB\/T/i.test(caption + ocr);
}

export function formatExtractedFacts(facts: Record<string, unknown> | null | undefined): string {
  if (!facts || Object.keys(facts).length === 0) {
    return "";
  }
  const labels: Record<string, string> = {
    cert_name: "证书名称",
    issue_date: "生效日期",
    expire_date: "失效日期",
    confidence: "置信度",
    information_role: "信息类型",
    role: "信息类型",
  };
  const skip = new Set(["information_role", "role", "confidence"]);
  return Object.entries(facts)
    .filter(([key, value]) => !skip.has(key) && value !== null && value !== undefined && String(value).trim())
    .map(([key, value]) => {
      const label = labels[key] ?? key;
      return `${label}：${String(value)}`;
    })
    .join("\n");
}

export function buildCoreImageSummaryLines(assets: ImageExtractionFields[]): string[] {
  const lines: string[] = [];
  for (const asset of assets) {
    if (!isCoreImageAsset(asset)) {
      continue;
    }
    const parts = [asset.image_caption, asset.image_ocr_text, formatExtractedFacts(asset.extracted_facts)]
      .map((part) => part?.trim())
      .filter(Boolean);
    if (parts.length) {
      lines.push(parts.join("；"));
    }
  }
  return lines;
}
