const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export function toAbsoluteMediaUrl(url: string): string {
  if (url.startsWith("http://") || url.startsWith("https://")) {
    return url;
  }
  if (url.startsWith("/")) {
    return `${API_BASE}${url}`;
  }
  return url;
}

export function resolveImageRefToMediaUrl(
  kbId: string,
  imageRef: string,
  imageRefMap: Record<string, string>,
): string | null {
  const ref = imageRef.trim().replace(/\\/g, "/");
  if (!ref) {
    return null;
  }
  if (imageRefMap[ref]) {
    return `/api/v1/kbs/${kbId}/media/${imageRefMap[ref]}`;
  }

  const basename = ref.split("/").pop() ?? ref;
  const candidates = [ref, `images/${basename}`, basename];
  if (!ref.includes("/")) {
    for (const ext of [".png", ".jpeg", ".jpg"]) {
      candidates.push(`images/${ref}${ext}`, `${ref}${ext}`);
    }
  }

  for (const key of candidates) {
    const assetId = imageRefMap[key];
    if (assetId) {
      return `/api/v1/kbs/${kbId}/media/${assetId}`;
    }
  }

  for (const [key, assetId] of Object.entries(imageRefMap)) {
    if (key === basename || key.endsWith(`/${basename}`)) {
      return `/api/v1/kbs/${kbId}/media/${assetId}`;
    }
  }
  return null;
}

export function resolveMarkdownImageSrc(
  src: string | undefined,
  kbId: string | undefined,
  imageRefMap: Record<string, string> | undefined,
): string | undefined {
  if (!src) {
    return undefined;
  }
  if (src.startsWith("/api/") || src.startsWith("http://") || src.startsWith("https://")) {
    return toAbsoluteMediaUrl(src);
  }
  if (kbId && imageRefMap) {
    const resolved = resolveImageRefToMediaUrl(kbId, src, imageRefMap);
    if (resolved) {
      return toAbsoluteMediaUrl(resolved);
    }
  }
  return undefined;
}
