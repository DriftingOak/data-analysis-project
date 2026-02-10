#!/usr/bin/env python3
"""
POLYMARKET BOT — LLM Market Classification & Filtering
========================================================
Uses GPT-4o-mini to classify and filter geopolitical candidates.
Same classification system as annotate.py (backtest), adapted for live use.

Returns per-market: exclude, domain, region, salience.
Batches candidates in a single API call for cost efficiency.
Cost: ~$0.003 per batch of 40 markets.

Usage:
    from llm_filter import llm_classify_candidates
    
    # candidates = list of objects with .question attribute
    valid, rejected = llm_classify_candidates(candidates)
    # valid candidates now have .llm_region, .llm_domain, .llm_salience set
"""

import os
import json
import requests
from typing import List, Tuple

# =============================================================================
# CONFIG
# =============================================================================

MODEL = "gpt-4o-mini"
API_URL = "https://api.openai.com/v1/chat/completions"

# Aligned with annotate.py from the backtesting pipeline
SYSTEM_PROMPT = """You are a geopolitical market classifier for a Polymarket trading bot.

STRATEGY CONTEXT: The bot bets NO on geopolitical prediction markets, exploiting salience bias — the public overestimates the probability of dramatic, spectacular events. Betting NO = betting "this dramatic thing does NOT happen."

For each market, provide a JSON classification.

## 1. EXCLUDE (should the bot trade this?)

EXCLUDE = false (TRADE IT) if:
- Wars, military operations, strikes, airstrikes, invasions, territorial control
- Bombing, shelling, missile launches, drone strikes, shoot-downs
- Nuclear tests, weapons proliferation, arms control violations
- Terrorism, hostage situations with international dimension
- Regime change, coups, revolutions, assassinations
- Ceasefires, peace agreements (NO = "no deal" = status quo)
- Sanctions, tariffs, trade wars between countries
- International diplomacy crises, treaty withdrawals
- Major confrontations (naval incidents, airspace violations, border clashes)
- Markets with specific dates/thresholds are fine (e.g. "Will X strike Y on Feb 10?")
- "Before [date]" markets are fine — core salience bets
- "Nothing Ever Happens" style markets — literally the thesis

EXCLUDE = true (SKIP IT) if:
- Not geopolitical: e-sports, crypto, entertainment, sports, weather, science, finance, tech
- Word mention bets ("Will X say 'Y' during speech?" — depends on word choice, not dramatic events)
- Meme/joke markets ("before GTA VI", "before Heat Death of Universe")
- Pure domestic politics with no violence/military dimension (approval ratings, pardons, court cases, legislation)
- Elections and polls (outcome is certain to happen, question is who wins — not a "nothing happens" bet)
- Market where NO doesn't mean "nothing dramatic happens"

## 2. DOMAIN
- "military": armed conflict, strikes, invasions, territorial control, troop movements, weapons
- "diplomatic": sanctions, treaties, international relations, trade wars, summits
- "domestic": elections, internal politics, leadership changes, legislation

## 3. REGION
- "ukraine-russia": Ukraine-Russia conflict, Crimea, Donbas, Kursk
- "middle-east": Israel, Palestine, Iran, Syria, Lebanon, Yemen, Iraq, Saudi Arabia, Gulf
- "asia": China, Taiwan, Korea, Japan, India, Pakistan, Southeast Asia
- "americas": US foreign policy, Latin America, Canada
- "europe": EU, UK, Balkans, Turkey, NATO (when not Ukraine-specific)
- "other": Africa, Oceania, or cannot determine

## 4. SALIENCE
- "high": major world powers directly involved, front-page global news, active crises
- "medium": regionally significant, covered by international press
- "low": obscure, niche, minor attention

## OUTPUT FORMAT

Return ONLY a JSON array, no markdown, no explanation:

[
  {"idx": 1, "exclude": false, "domain": "military", "region": "middle-east", "salience": "high"},
  {"idx": 2, "exclude": true, "exclude_reason": "word-mention", "domain": "domestic", "region": "americas", "salience": "medium"}
]

Always include idx matching the market number. If exclude=true, add exclude_reason (short phrase)."""


USER_PROMPT_TEMPLATE = """Classify these {n} markets:

{markets}"""


# =============================================================================
# CORE
# =============================================================================

def llm_classify_candidates(candidates: list, batch_size: int = 50) -> Tuple[list, list]:
    """Classify and filter candidates via LLM.
    
    Returns (valid, rejected).
    Valid candidates get .llm_region, .llm_domain, .llm_salience attributes set.
    If no API key, returns all as valid (passthrough).
    """
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        print("[LLM] No OPENAI_API_KEY — skipping classification")
        return candidates, []

    if not candidates:
        return [], []

    valid = []
    rejected = []

    for i in range(0, len(candidates), batch_size):
        batch = candidates[i:i + batch_size]
        batch_valid, batch_rejected = _classify_batch(batch, api_key)
        valid.extend(batch_valid)
        rejected.extend(batch_rejected)

    return valid, rejected


def _classify_batch(candidates: list, api_key: str) -> Tuple[list, list]:
    """Classify a single batch."""
    # Build market list
    lines = []
    for idx, c in enumerate(candidates, 1):
        q = c.question if hasattr(c, 'question') else c.get('question', '?')
        lines.append(f"{idx}. {q}")

    user_prompt = USER_PROMPT_TEMPLATE.format(n=len(candidates), markets="\n".join(lines))

    # API call
    try:
        resp = requests.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0,
                "max_tokens": len(candidates) * 60,
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()

    except Exception as e:
        print(f"[LLM] API error: {e} — passing all through")
        return candidates, []

    # Parse
    content = data["choices"][0]["message"]["content"].strip()
    classifications = _parse_json_response(content, len(candidates))

    # Usage
    usage = data.get("usage", {})
    cost = (usage.get("prompt_tokens", 0) * 0.15 + usage.get("completion_tokens", 0) * 0.6) / 1_000_000

    # Apply classifications
    valid = []
    rejected = []

    for c, cls in zip(candidates, classifications):
        q = c.question if hasattr(c, 'question') else c.get('question', '?')

        if cls.get("exclude", False):
            reason = cls.get("exclude_reason", "unknown")
            print(f"[LLM] ❌ {reason:20s} | {q[:60]}")
            rejected.append(c)
        else:
            # Attach classification to candidate
            raw_region = cls.get("region", "other")
            # Map to existing cluster names
            REGION_TO_CLUSTER = {
                "ukraine-russia": "ukraine",
                "middle-east": "mideast",
                "asia": "china",
                "americas": "other",
                "europe": "other",
                "other": "other",
            }
            c.llm_region = REGION_TO_CLUSTER.get(raw_region, "other")
            c.llm_domain = cls.get("domain", "international")
            c.llm_salience = cls.get("salience", "medium")
            valid.append(c)

    n_valid = len(valid)
    n_rejected = len(rejected)
    print(f"[LLM] Batch: {n_valid}✅ {n_rejected}❌ | ${cost:.4f}")

    return valid, rejected


def _parse_json_response(content: str, expected_count: int) -> list:
    """Parse JSON array from LLM response."""
    # Strip markdown fences
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    if text.startswith("json"):
        text = text[4:].strip()

    try:
        items = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"[LLM] JSON parse error: {e}")
        print(f"[LLM] Response: {text[:200]}")
        return [{"exclude": False}] * expected_count

    # Map by idx
    by_idx = {}
    for item in items:
        idx = item.get("idx")
        if idx is not None:
            by_idx[idx] = item

    # Build ordered list, filling gaps with defaults
    result = []
    for i in range(1, expected_count + 1):
        if i in by_idx:
            result.append(by_idx[i])
        else:
            result.append({"exclude": False})

    return result


# =============================================================================
# BACKWARD COMPAT
# =============================================================================

def llm_validate_candidates(candidates: list, batch_size: int = 50) -> Tuple[list, list]:
    """Alias for llm_classify_candidates."""
    return llm_classify_candidates(candidates, batch_size)


# =============================================================================
# STANDALONE TEST
# =============================================================================

if __name__ == "__main__":
    class FakeCandidate:
        def __init__(self, q):
            self.question = q
            self.llm_region = None
            self.llm_domain = None
            self.llm_salience = None

    test_markets = [
        FakeCandidate("Will Israel strike Lebanon on February 10, 2026?"),
        FakeCandidate("Russia-Ukraine Ceasefire before GTA VI?"),
        FakeCandidate("Will Trump mention 'nuclear' in his UN speech?"),
        FakeCandidate("Nothing Ever Happens: US Strike Edition"),
        FakeCandidate("Will the US strike 2 countries in February 2026?"),
        FakeCandidate("Will China invade Taiwan before March 2026?"),
        FakeCandidate("Will Bitcoin reach $100k?"),
        FakeCandidate("Will Zelensky say 'Putin' during address?"),
        FakeCandidate("Will North Korea conduct a nuclear test in 2026?"),
        FakeCandidate("German federal election — CDU majority?"),
        FakeCandidate("Will Iran enrich uranium to 90% by June?"),
        FakeCandidate("Will Russia capture Pokrovsk by March 31?"),
    ]

    valid, rejected = llm_classify_candidates(test_markets)

    print(f"\n{'='*70}")
    print(f"Valid: {len(valid)}")
    for c in valid:
        print(f"  ✅ [{c.llm_region:15s}] [{c.llm_domain:10s}] [{c.llm_salience:6s}] {c.question}")
    print(f"\nRejected: {len(rejected)}")
    for c in rejected:
        print(f"  ❌ {c.question}")
