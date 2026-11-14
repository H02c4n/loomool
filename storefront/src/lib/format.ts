export function formatSek(cents: number, currency = "SEK"): string {
  const amount = cents / 100;
  return new Intl.NumberFormat("sv-SE", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(amount);
}

export function rewriteMediaUrl(url: string | null): string | null {
  if (!url) return null;
  // Backend generates http://minio:9000/loomool-media/<key>...
  // Browser-accessible path is /media/<key> (proxied by Next.js).
  const match = url.match(/^https?:\/\/minio:9000\/loomool-media\/(.+)$/);
  return match ? `/media/${match[1]}` : url;
}

export function productTypeLabel(type: string): string {
  const map: Record<string, string> = {
    DIY_KIT: "DIY kit",
    MATERIAL: "Material",
    FINISHED_HANDMADE: "Finished handmade",
    DIGITAL_PATTERN: "Digital pattern",
    WORKSHOP: "Workshop",
    BUNDLE: "Bundle",
  };
  return map[type] ?? type;
}
