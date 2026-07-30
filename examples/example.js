// KLineAPI JavaScript Example
// Run with: node klineapi_example.js

const API = "https://klineapi.com/v1";

async function fetchData(endpoint, params = {}) {
  const url = new URL(API + "/" + endpoint);
  Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));

  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function main() {
  // Get market indices
  const market = await fetchData("market");
  console.log("=== Market ===");
  market.data?.forEach(idx =>
    console.log(`${idx.name}: ${idx.price} (${idx.changepercent}%)`)
  );

  // Get limit-up stocks
  const limitUp = await fetchData("limit-up");
  console.log(`\n=== Limit-up: ${limitUp.total || 0} stocks ===`);
  limitUp.slice(0, 3).forEach(s =>
    console.log(`${s.code} ${s.name}: +${s.changepercent}%`)
  );

  // Get quote
  const quote = await fetchData("quote", { code: "600519" });
  console.log(`\n=== Moutai ===`);
  console.log(`Price: ${quote.price}, Change: ${quote.changepercent}%`);
}

main().catch(console.error);
