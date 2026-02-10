#!/usr/bin/env python3
"""
POLYMARKET BOT — LLM Market Classification & Filtering
========================================================
Uses GPT-4o-mini to classify and filter geopolitical candidates.
Same classification system as annotate.py (backtest), adapted for live use.

Returns per-market: exclude, domain, region, salience.
Batches candidates in parallel API calls for speed.
Cost: ~$0.005 per run (~400 markets).

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
from concurrent.futures import ThreadPoolExecutor, as_completed

# =============================================================================
# CONFIG
# =============================================================================

MODEL = "gpt-4o-mini"
API_URL = "https://api.openai.com/v1/chat/completions"

REGION_TO_CLUSTER = {
    "ukraine-russia": "ukraine",
    "middle-east": "mideast",
    "asia": "china",
    "americas": "other",
    "europe": "other",
    "other": "other",
}

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
- Leadership changes of leaders directly commanding active military conflicts (e.g. "Netanyahu out", "Zelenskyy out", "Putin out", "Khamenei out") — their departure directly changes the course of ongoing wars. Does NOT include US presidents, EU leaders, or other leaders whose departure is primarily a domestic political event.
- Ceasefires, peace deals, peace agreements, nuclear deals between countries — ALWAYS INCLUDE. NO = "no deal happens" = status quo continues = core thesis bet.
- Sanctions, tariffs, trade wars between countries
- International diplomacy crises, treaty withdrawals
- Major confrontations (naval incidents, airspace violations, border clashes)
- Markets with specific dates/thresholds (e.g. "Will X strike Y on Feb 10?")
- "Before [date]" markets — core salience bets
- "Nothing Ever Happens" style markets — literally the thesis

EXCLUDE = true (SKIP IT) if:
- Not geopolitical: e-sports, crypto, entertainment, sports, weather, science, finance, tech
- Word mention bets ("Will X say 'Y' during speech?")
- Meme/joke time anchors: any market containing "before GTA VI", "before Heat Death of Universe", or similar absurd deadlines — even if the underlying event is geopolitical
- US domestic politics by default: elections, appointments, pardons, court cases, legislation, approval ratings, congressional votes, impeachment, cabinet nominations. ONLY include US politics if the market directly involves military action abroad (e.g. "Will US strike Iran?" = VALID, "Will Trump fire Secretary of Defense?" = REJECT)
- Elections and polls in countries NOT involved in active conflicts
- Pure domestic politics with no violence/military dimension
- Market where NO doesn't mean "nothing dramatic happens"

## CRITICAL EXAMPLES (follow these exactly)

✅ INCLUDE (exclude=false):
1. "Russia x Ukraine ceasefire by March 31" → military, ukraine-russia (NO = no peace = status quo)
2. "Russia x Ukraine ceasefire by end of 2026" → military, ukraine-russia (NO = no peace = status quo)
3. "Ukraine signs peace deal with Russia by June 30" → diplomatic, ukraine-russia (NO = no deal)
4. "US-Iran nuclear deal by June 30" → diplomatic, middle-east (NO = no deal = status quo)
5. "US-Iran nuclear deal before 2027" → diplomatic, middle-east (NO = no deal)
6. "Netanyahu out by end of 2026" → domestic, middle-east (wartime leader commanding active conflict)
7. "Zelenskyy out as Ukraine president by end of 2026" → domestic, ukraine-russia (wartime leader)
8. "Putin out as President of Russia by June 30" → domestic, ukraine-russia (wartime leader)
9. "Khamenei out as Supreme Leader of Iran by March 31" → domestic, middle-east (wartime leader)
10. "Will Israel strike Lebanon on February 10?" → military, middle-east
11. "US strikes Iran by March 31" → military, middle-east
12. "Nothing Ever Happens: US Strike Edition" → military, other
13. "Will Russia capture Pokrovsk by March 31?" → military, ukraine-russia
14. "China x Taiwan military clash before 2027" → military, asia
15. "Hezbollah strike on Israel by March 31" → military, middle-east
16. "Will the US capture Khamenei before 2027?" → military, middle-east
17. "Will Russia invade another country in 2026?" → military, ukraine-russia
18. "Israel x Hamas Ceasefire Phase II by March 31?" → diplomatic, middle-east (NO = no ceasefire)

❌ EXCLUDE (exclude=true):
19. "China invades Taiwan before GTA VI" → meme time anchor (exclude even though event is geopolitical)
20. "Russia-Ukraine Ceasefire before GTA VI" → meme time anchor
21. "Will JD Vance win the 2028 US Presidential Election?" → US domestic politics
22. "Will Trump fire the Secretary of Defense?" → US domestic politics
23. "Will Vicky Dávila win the 2026 Colombian presidential election?" → election, no active conflict
24. "Will Wagner Moura win Best Actor at the Academy Awards?" → entertainment
25. "Will Trump mention 'nuclear' in his UN speech?" → word-mention bet

## 2. DOMAIN
- "military": armed conflict, strikes, invasions, territorial control, troop movements, weapons
- "diplomatic": sanctions, treaties, international relations, trade wars, ceasefires, peace deals, nuclear deals
- "domestic": internal politics, leadership changes, legislation

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

## MANDATORY — NEVER EXCLUDE THESE (override all other rules):
- ANY market about military strikes, airstrikes, bombing, shelling, invasions, territorial capture, ground offensives. These are ALWAYS exclude=false. "Will X strike Y" = ALWAYS INCLUDE.
- ANY market about ceasefires, peace deals, or nuclear deals. ALWAYS exclude=false.
- ANY market about Netanyahu, Zelenskyy, Putin, Khamenei, Xi Jinping, Kim Jong Un leaving power/being removed. These are wartime/crisis leaders. ALWAYS exclude=false, domain="domestic".
- ANY market about regime change, coups, or assassinations of world leaders. ALWAYS exclude=false.

If in doubt, set exclude=false. The bot's edge comes from volume — rejecting valid markets costs more than including a few marginal ones.

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

def llm_classify_candidates(candidates: list, batch_size: int = 100) -> Tuple[list, list]:
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

    # Build batches
    batches = [candidates[i:i + batch_size] for i in range(0, len(candidates), batch_size)]

    valid = []
    rejected = []

    # Parallel LLM calls (up to 4 concurrent)
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(_classify_batch, batch, api_key): i
            for i, batch in enumerate(batches)
        }
        for future in as_completed(futures):
            batch_idx = futures[future]
            try:
                batch_valid, batch_rejected = future.result()
                valid.extend(batch_valid)
                rejected.extend(batch_rejected)
            except Exception as e:
                print(f"[LLM] Batch {batch_idx} failed: {e} — passing through")
                valid.extend(batches[batch_idx])

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
            timeout=120,
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

def llm_validate_candidates(candidates: list, batch_size: int = 100) -> Tuple[list, list]:
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
        # Should INCLUDE
        FakeCandidate("Will Israel strike Lebanon on February 10, 2026?"),
        FakeCandidate("Nothing Ever Happens: US Strike Edition"),
        FakeCandidate("Will the US strike 2 countries in February 2026?"),
        FakeCandidate("Will China invade Taiwan before March 2026?"),
        FakeCandidate("Will North Korea conduct a nuclear test in 2026?"),
        FakeCandidate("Will Iran enrich uranium to 90% by June?"),
        FakeCandidate("Will Russia capture Pokrovsk by March 31?"),
        FakeCandidate("Netanyahu out by end of 2026?"),
        FakeCandidate("Zelenskyy out as Ukraine president by end of 2026?"),
        FakeCandidate("Putin out as President of Russia by June 30?"),
        FakeCandidate("Khamenei out as Supreme Leader of Iran by March 31?"),
        FakeCandidate("Russia x Ukraine ceasefire by end of 2026?"),
        FakeCandidate("Russia x Ukraine ceasefire by March 31, 2026?"),
        FakeCandidate("Ukraine signs peace deal with Russia by March 31?"),
        FakeCandidate("Ukraine signs peace deal with Russia before 2027?"),
        FakeCandidate("US-Iran nuclear deal before 2027?"),
        FakeCandidate("US-Iran nuclear deal by June 30?"),
        FakeCandidate("Israel x Hamas Ceasefire Phase II by March 31?"),
        FakeCandidate("Will Russia invade another country in 2026?"),
        # Should EXCLUDE
        FakeCandidate("Russia-Ukraine Ceasefire before GTA VI?"),
        FakeCandidate("Will China invades Taiwan before GTA VI?"),
        FakeCandidate("Will Trump mention 'nuclear' in his UN speech?"),
        FakeCandidate("Will Bitcoin reach $100k?"),
        FakeCandidate("Will Zelensky say 'Putin' during address?"),
        FakeCandidate("German federal election — CDU majority?"),
        FakeCandidate("Will JD Vance win the 2028 US Presidential Election?"),
        FakeCandidate("Will Trump fire the Secretary of Defense?"),
        FakeCandidate("Will Vicky Dávila win the 2026 Colombian presidential election?"),
        FakeCandidate("Will Wagner Moura win Best Actor at the Academy Awards?"),
    ]

    valid, rejected = llm_classify_candidates(test_markets)

    print(f"\n{'='*70}")
    print(f"Valid: {len(valid)}")
    for c in valid:
        print(f"  ✅ [{c.llm_region:15s}] [{c.llm_domain:10s}] [{c.llm_salience:6s}] {c.question}")
    print(f"\nRejected: {len(rejected)}")
    for c in rejected:
        print(f"  ❌ {c.question}")

    # Automated check
    valid_qs = {c.question for c in valid}
    rejected_qs = {c.question for c in rejected}

    should_include = [
        "Will Israel strike Lebanon on February 10, 2026?",
        "Nothing Ever Happens: US Strike Edition",
        "Will the US strike 2 countries in February 2026?",
        "Will China invade Taiwan before March 2026?",
        "Will North Korea conduct a nuclear test in 2026?",
        "Will Iran enrich uranium to 90% by June?",
        "Will Russia capture Pokrovsk by March 31?",
        "Netanyahu out by end of 2026?",
        "Zelenskyy out as Ukraine president by end of 2026?",
        "Putin out as President of Russia by June 30?",
        "Khamenei out as Supreme Leader of Iran by March 31?",
        "Russia x Ukraine ceasefire by end of 2026?",
        "Russia x Ukraine ceasefire by March 31, 2026?",
        "Ukraine signs peace deal with Russia by March 31?",
        "Ukraine signs peace deal with Russia before 2027?",
        "US-Iran nuclear deal before 2027?",
        "US-Iran nuclear deal by June 30?",
        "Israel x Hamas Ceasefire Phase II by March 31?",
        "Will Russia invade another country in 2026?",
    ]
    should_exclude = [
        "Russia-Ukraine Ceasefire before GTA VI?",
        "Will China invades Taiwan before GTA VI?",
        "Will Trump mention 'nuclear' in his UN speech?",
        "Will Bitcoin reach $100k?",
        "Will Zelensky say 'Putin' during address?",
        "Will JD Vance win the 2028 US Presidential Election?",
        "Will Trump fire the Secretary of Defense?",
        "Will Vicky Dávila win the 2026 Colombian presidential election?",
        "Will Wagner Moura win Best Actor at the Academy Awards?",
        "German federal election — CDU majority?",
    ]

    errors = 0
    print(f"\n{'='*70}")
    print("VALIDATION")
    for q in should_include:
        if q not in valid_qs:
            print(f"  ❗ MISSED (should be valid): {q}")
            errors += 1
    for q in should_exclude:
        if q not in rejected_qs:
            print(f"  ❗ LEAKED (should be rejected): {q}")
            errors += 1

    if errors == 0:
        print("  ✅ ALL 29 CHECKS PASSED")
    else:
        print(f"  ⚠️  {errors} ERROR(S)")
