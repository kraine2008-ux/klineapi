#!/usr/bin/env python3
"""Unofficial KLineAPI Python client"""
import httpx
from typing import Optional, Dict, Any, List


class KLineAPI:
    """KLineAPI client - A-share real-time stock data"""
    
    BASE = "https://klineapi.com/v1"
    
    def __init__(self, api_key: str):
        self.client = httpx.Client(headers={"X-API-Key": api_key}, timeout=15)
    
    def quote(self, code: str) -> Dict[str, Any]:
        """Get real-time quote for a stock"""
        r = self.client.get(f"{self.BASE}/quote", params={"code": code})
        r.raise_for_status()
        return r.json()
    
    def limit_up(self) -> List[Dict[str, Any]]:
        """Get today's limit-up stocks"""
        r = self.client.get(f"{self.BASE}/limit-up")
        r.raise_for_status()
        return r.json()
    
    def market(self) -> Dict[str, Any]:
        """Get market indices (Shanghai/Shenzhen/ChiNext)"""
        r = self.client.get(f"{self.BASE}/market")
        r.raise_for_status()
        return r.json()
    
    def board(self, sort: str = "changepercent") -> List[Dict[str, Any]]:
        """Get full market ranking sorted by field"""
        r = self.client.get(f"{self.BASE}/board", params={"sort": sort})
        r.raise_for_status()
        return r.json()
    
    def sector(self) -> List[Dict[str, Any]]:
        """Get sector/industry ranking"""
        r = self.client.get(f"{self.BASE}/sector")
        r.raise_for_status()
        return r.json()


# CLI usage
if __name__ == "__main__":
    import sys
    key = sys.argv[1] if len(sys.argv) > 1 else input("API Key: ")
    api = KLineAPI(key)
    
    print("=== Market Indices ===")
    m = api.market()
    for idx in m.get("data", []):
        print(f"  {idx['name']}: {idx['price']} ({idx['changepercent']}%)")
    
    print("\n=== Top 5 Limit-Up ===")
    lu = api.limit_up()[:5]
    for s in lu:
        print(f"  {s['code']} {s['name']}: +{s.get('changepercent','?')}%")
