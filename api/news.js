// Clickdy Blog & News — allowlisted RSS headline endpoint for Vercel.
// Only titles, dates, publisher names and links are returned. Full stories stay on publisher websites.
const FEEDS = [
  { source: "OpenAI", category: "AI", feed: "https://openai.com/news/rss.xml", allowed: ["openai.com"] },
  { source: "Google Research", category: "AI & Research", feed: "https://research.google/blog/rss/", allowed: ["research.google"] },
  { source: "Google DeepMind", category: "AI", feed: "https://deepmind.google/blog/rss.xml", allowed: ["deepmind.google"] },
  { source: "NASA Technology", category: "Technology & Science", feed: "https://www.nasa.gov/rss/dyn/breaking_news.rss", allowed: ["nasa.gov"] }
];
const MAX_PER_FEED = 5;
const TIMEOUT_MS = 7000;

function decodeEntities(value) {
  const named = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " " };
  return String(value || "")
    .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, "$1")
    .replace(/&#(\d+);/g, (_, n) => { const cp = Number(n); return cp > 0 && cp <= 0x10ffff ? String.fromCodePoint(cp) : ""; })
    .replace(/&#x([0-9a-f]+);/gi, (_, n) => { const cp = parseInt(n, 16); return cp > 0 && cp <= 0x10ffff ? String.fromCodePoint(cp) : ""; })
    .replace(/&([a-z]+);/gi, (whole, name) => named[name.toLowerCase()] || whole)
    .replace(/<[^>]*>/g, "")
    .replace(/\s+/g, " ")
    .trim();
}
function tagText(block, tagNames) {
  for (const tag of tagNames) {
    const re = new RegExp("<(?:[\\w.-]+:)?" + tag + "\\b[^>]*>([\\s\\S]*?)<\\/(?:[\\w.-]+:)?" + tag + "\\s*>", "i");
    const match = block.match(re);
    if (match) return decodeEntities(match[1]);
  }
  return "";
}
function itemUrl(block) {
  // RSS 2.0 <link>URL</link>
  const rss = block.match(/<(?:[\w.-]+:)?link\b[^>]*>([\s\S]*?)<\/(?:[\w.-]+:)?link\s*>/i);
  if (rss) return decodeEntities(rss[1]);
  // Atom <link href="URL" rel="alternate" />
  const links = [...block.matchAll(/<(?:[\w.-]+:)?link\b([^>]*)\/?>/gi)];
  for (const match of links) {
    const attrs = match[1];
    const rel = (attrs.match(/\brel\s*=\s*["']([^"']+)["']/i) || [])[1];
    const href = (attrs.match(/\bhref\s*=\s*["']([^"']+)["']/i) || [])[1];
    if (href && (!rel || rel === "alternate")) return decodeEntities(href);
  }
  return "";
}
function safePublisherUrl(value, allowed) {
  try {
    const url = new URL(value);
    if (url.protocol !== "https:") return "";
    if (!allowed.some(domain => url.hostname === domain || url.hostname.endsWith("." + domain))) return "";
    return url.toString();
  } catch (_) { return ""; }
}
function parseFeed(xml, feed) {
  const blocks = [...xml.matchAll(/<(item|entry)\b[^>]*>([\s\S]*?)<\/\1\s*>/gi)].map(m => m[2]);
  const results = [];
  for (const block of blocks.slice(0, 25)) {
    const title = tagText(block, ["title"]);
    const url = safePublisherUrl(itemUrl(block), feed.allowed);
    const dateRaw = tagText(block, ["pubDate", "published", "updated", "date", "dc:date"]);
    const parsedDate = dateRaw ? new Date(dateRaw) : null;
    if (!title || !url) continue;
    results.push({
      title: title.slice(0, 240),
      url,
      source: feed.source,
      category: feed.category,
      publishedAt: parsedDate && !Number.isNaN(parsedDate.getTime()) ? parsedDate.toISOString() : null,
      date: parsedDate && !Number.isNaN(parsedDate.getTime())
        ? parsedDate.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" })
        : "Latest update"
    });
    if (results.length >= MAX_PER_FEED) break;
  }
  return results;
}
async function loadFeed(feed) {
  try {
    const response = await fetch(feed.feed, {
      headers: { "user-agent": "Clickdy-News-Radar/1.0 (+https://clickdy.vercel.app/blog/)", "accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.5" },
      signal: AbortSignal.timeout(TIMEOUT_MS)
    });
    if (!response.ok) throw new Error("Feed returned " + response.status);
    const xml = await response.text();
    if (!xml || xml.length > 2_000_000) throw new Error("Feed response invalid or too large");
    return parseFeed(xml, feed);
  } catch (_) {
    // A feed may be temporarily unavailable or its URL may change. The frontend includes official source-page fallbacks.
    return [];
  }
}
module.exports = async function handler(req, res) {
  res.setHeader("Cache-Control", "public, s-maxage=600, stale-while-revalidate=1800");
  res.setHeader("X-Content-Type-Options", "nosniff");
  if (req.method !== "GET") {
    res.setHeader("Allow", "GET");
    return res.status(405).json({ error: "Method not allowed" });
  }
  const groups = await Promise.all(FEEDS.map(loadFeed));
  const items = groups.flat().sort((a, b) => {
    const ad = a.publishedAt ? Date.parse(a.publishedAt) : 0;
    const bd = b.publishedAt ? Date.parse(b.publishedAt) : 0;
    return bd - ad;
  }).slice(0, 12);
  return res.status(200).json({
    items,
    updatedAt: new Date().toISOString(),
    sourcesChecked: FEEDS.length,
    note: "Headlines and links are attributed to their publishers. Open the publisher link for the full story."
  });
};
