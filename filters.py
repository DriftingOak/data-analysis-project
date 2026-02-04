"""
POLYMARKET BOT - Unified Filters
=================================
Two filtering levels:
1. CAPTURE (broad): For snapshots - excludes obvious garbage (sports, crypto, entertainment)
2. TRADING (strict): For bot - requires ENTITY + ACTION

Usage:
    from filters import is_garbage, is_geopolitical, get_cluster
    
    # Snapshot pipeline
    if not is_garbage(question):
        capture_market(...)
    
    # Trading pipeline  
    if is_geopolitical(question):
        trade_market(...)
"""

import re
from typing import Tuple, Optional, Set
from dataclasses import dataclass

FILTER_VERSION = "v2.0"

# =============================================================================
# CAPTURE FILTER (Broad) - For Snapshots
# =============================================================================
# On exclut UNIQUEMENT le déchet évident
# Tout le reste est capturé, même si pas géopolitique

GARBAGE_KEYWORDS: Set[str] = {
    # --- SPORTS ---
    "nfl", "nba", "mlb", "nhl", "mls", "ufc", "wwe", "pga", "lpga",
    "premier league", "la liga", "serie a", "bundesliga", "ligue 1",
    "champions league", "europa league", "world cup", "euro 2024", "euro 2028",
    "super bowl", "stanley cup", "world series", "march madness",
    "touchdown", "quarterback", "rushing yards", "receiving yards",
    "rebounds", "assists", "three-pointers", "free throws",
    "home run", "strikeout", "batting average", "era",
    "goals scored", "clean sheet", "penalty kick", "yellow card",
    "knockout", "submission", "tale of the tape", "weigh-in",
    "tennis", "wimbledon", "us open", "french open", "australian open",
    "golf", "masters", "pga championship", "the open",
    "f1", "formula 1", "nascar", "indycar", "motogp",
    "olympics", "paralympics", "medal count",
    "esports", "counter-strike", "valorant", "league of legends", "dota",
    "fortnite", "call of duty", "overwatch",
    # Teams
    "lakers", "celtics", "warriors", "heat", "bulls", "knicks", "nets",
    "cowboys", "patriots", "chiefs", "eagles", "packers",
    "bulldogs", "crimson tide", "buckeyes", "wolverines",
    "yankees", "dodgers", "red sox", "cubs",
    
    # --- CRYPTO PRICES ---
    "bitcoin price", "btc price", "ethereum price", "eth price",
    "solana price", "sol price", "crypto price", "token price",
    "memecoin", "meme coin", "nft drop", "airdrop",
    "all time high", "ath", "market cap",
    
    # --- ENTERTAINMENT ---
    "movie", "film release", "box office", "netflix", "disney+", "hbo",
    "album drop", "song", "grammy", "emmy", "oscar", "golden globe",
    "taylor swift", "drake album", "kanye", "kardashian",
    "bachelor", "bachelorette", "survivor", "big brother",
    "youtube subscribers", "tiktok followers", "twitch",
    "streamer", "influencer",
    
    # --- GAMING (non-esports) ---
    "speedrun", "world record gaming", "video game release",
    
    # --- WEATHER/NATURAL (non-geopolitical) ---
    "earthquake magnitude", "hurricane category", "tornado",
    "tsunami warning", "volcano eruption",
}

# Patterns regex pour les cas plus complexes
GARBAGE_PATTERNS = [
    r"\b(nba|nfl|mlb|nhl|ufc|mma)\b",
    r"\b(rebounds?|assists?|touchdowns?|strikeouts?)\b",
    r"\bover/under\b",
    r"\bo/u\s*\d",  # "O/U 5.5"
    r"\b(spread|moneyline|parlay)\b",
    r"\bvs\.?\s+[A-Z][a-z]+\s+(heat|lakers|warriors|celtics|bulls)",  # Teams
]

_GARBAGE_RX = [re.compile(p, re.IGNORECASE) for p in GARBAGE_PATTERNS]


def is_garbage(question: str) -> Tuple[bool, str]:
    """
    Check if market is obvious garbage (sports, crypto prices, entertainment).
    
    Returns:
        (is_garbage, reason)
    """
    if not question:
        return True, "empty"
    
    q = question.lower()
    
    # Check keywords
    for kw in GARBAGE_KEYWORDS:
        if kw in q:
            return True, f"garbage_kw:{kw}"
    
    # Check patterns
    for rx in _GARBAGE_RX:
        if rx.search(q):
            return True, f"garbage_pattern"
    
    return False, ""


def should_capture(question: str) -> Tuple[bool, str]:
    """
    Should this market be captured in snapshot?
    Inverse of is_garbage with clearer semantics.
    
    Returns:
        (should_capture, reason)
    """
    is_junk, reason = is_garbage(question)
    if is_junk:
        return False, reason
    return True, "ok"


# =============================================================================
# TRADING FILTER (Strict) - For Bot
# =============================================================================
# Requires ENTITY + ACTION to be considered geopolitical

# --- ENTITIES (countries, leaders, orgs) ---
# Keywords that need word boundaries (short or ambiguous)
ENTITIES_WORD_BOUNDARY: Set[str] = {
    "us", "uk", "eu", "un", "uae",
    "iran", "iraq", "cuba", "gaza", "mali", "chad",
    "nato", "idf", "cia", "fbi", "gru", "fsb", "sdf",
    "assad", "modi",
}

# Safe entities (can use substring match)
ENTITIES_SAFE: Set[str] = {
    # Major countries
    "russia", "russian", "ukraine", "ukrainian", "china", "chinese",
    "taiwan", "taiwanese", "israel", "israeli", "palestine", "palestinian",
    "venezuela", "venezuelan", "syria", "syrian", "lebanon", "lebanese",
    "north korea", "south korea", "korean",
    "afghanistan", "pakistan", "pakistani", "saudi", "yemen", "yemeni",
    "turkey", "turkish", "egypt", "egyptian", "libya", "libyan",
    "belarus", "belarusian", "crimea", "crimean",
    "mexico", "mexican", "colombia", "colombian",
    "japan", "japanese", "philippines", "filipino",
    "vietnam", "vietnamese", "myanmar", "burma",
    "india", "indian", "kashmir",
    "sudan", "sudanese", "ethiopia", "ethiopian", "somalia", "somalian",
    
    # Key cities
    "kyiv", "kiev", "kharkiv", "mariupol", "bakhmut", "pokrovsk",
    "moscow", "beijing", "taipei", "tehran", "damascus", "beirut",
    "jerusalem", "tel aviv", "gaza city", "rafah",
    "caracas", "pyongyang", "seoul", "kabul", "islamabad",
    
    # Leaders (current + recent)
    "putin", "zelensky", "zelenskyy", "khamenei", "netanyahu",
    "xi jinping", "kim jong", "maduro", "erdogan", "lukashenko",
    "lavrov", "shoigu", "nasrallah", "sinwar", "gallant",
    
    # Organizations
    "hamas", "hezbollah", "houthi", "houthis", "taliban", "wagner",
    "irgc", "mossad", "kremlin", "pentagon",
    "united nations", "security council", "european union",
}

# --- ACTIONS (verbs and conflict concepts) ---
ACTIONS: Set[str] = {
    # Military actions
    "invasion", "invade", "invaded", "invades",
    "strike", "strikes", "struck", "airstrike", "air strike",
    "missile", "drone strike", "bombing", "bomb", "bombed",
    "attack", "attacked", "attacks", "offensive",
    "capture", "captured", "captures", "seize", "seized",
    "advance", "advancing", "retreat", "retreating",
    "counteroffensive", "counter-offensive",
    "occupy", "occupied", "occupation",
    "annex", "annexed", "annexation",
    "blockade", "siege", "encircle",
    "deploy", "deployed", "deployment",
    "shell", "shelling", "artillery",
    "clash", "clashes", "clashed",
    
    # Peace/diplomacy
    "ceasefire", "cease-fire", "truce", "armistice",
    "peace deal", "peace treaty", "peace talks", "peace agreement",
    "negotiate", "negotiation", "negotiations",
    "summit", "diplomatic talks",
    "disarm", "disarmament",
    
    # Political change
    "regime change", "regime fall", "fall of",
    "coup", "uprising", "revolution", "revolt",
    "resign", "resigns", "resignation",
    "oust", "ousted", "topple", "toppled", "overthrow",
    "assassinate", "assassination",
    
    # Sanctions/economic
    "sanctions", "sanction", "sanctioned",
    "embargo", "embargoed",
    "tariff", "tariffs",
    
    # Escalation
    "escalation", "escalate", "escalates",
    "nuclear", "atomic", "warhead",
    "war", "warfare", "conflict",
    
    # Casualties/humanitarian
    "casualties", "killed", "deaths",
    "hostage", "hostages", "prisoner",
    "war crime", "genocide", "atrocity",
    
    # Status markers (for "X out as leader by...")
    "out as", "out by", "removed as", "no longer",
    "president", "prime minister", "leader",
    "remain", "remains",
}

# Pre-compile regex for word boundary entities
_ENTITY_WB_PATTERNS = {
    kw: re.compile(r'\b' + re.escape(kw) + r'\b', re.IGNORECASE)
    for kw in ENTITIES_WORD_BOUNDARY
}


def _has_entity(q: str) -> bool:
    """Check if text contains a geopolitical entity."""
    # Check word-boundary entities
    for kw, pattern in _ENTITY_WB_PATTERNS.items():
        if pattern.search(q):
            return True
    
    # Check safe entities (substring match)
    for kw in ENTITIES_SAFE:
        if kw in q:
            return True
    
    return False


def _has_action(q: str) -> bool:
    """Check if text contains a geopolitical action."""
    for kw in ACTIONS:
        if kw in q:
            return True
    return False


def is_geopolitical(question: str) -> bool:
    """
    Check if market is geopolitical (strict: ENTITY + ACTION).
    
    Returns:
        True if should be considered for trading
    """
    if not question:
        return False
    
    q = question.lower()
    
    # First check it's not garbage
    if is_garbage(q)[0]:
        return False
    
    # Must have both entity AND action
    return _has_entity(q) and _has_action(q)


def get_geo_match_details(question: str) -> dict:
    """
    Debug helper: return what matched.
    """
    q = question.lower()
    
    entities_found = []
    actions_found = []
    
    # Check entities
    for kw, pattern in _ENTITY_WB_PATTERNS.items():
        if pattern.search(q):
            entities_found.append(f"{kw}(wb)")
    for kw in ENTITIES_SAFE:
        if kw in q:
            entities_found.append(kw)
    
    # Check actions
    for kw in ACTIONS:
        if kw in q:
            actions_found.append(kw)
    
    return {
        "entities": entities_found,
        "actions": actions_found,
        "is_geo": bool(entities_found and actions_found),
    }


# =============================================================================
# CLUSTER ASSIGNMENT
# =============================================================================

CLUSTERS = {
    "ukraine": [
        "ukraine", "ukrainian", "kyiv", "kiev", "kharkiv", "mariupol",
        "bakhmut", "pokrovsk", "zelensky", "zelenskyy", "crimea",
        # Russia included here because most Russia markets are about Ukraine war
        "russia", "russian", "putin", "moscow", "kremlin",
    ],
    "mideast": [
        "israel", "israeli", "gaza", "palestine", "palestinian",
        "iran", "iranian", "tehran", "khamenei",
        "lebanon", "lebanese", "beirut", "hezbollah", "nasrallah",
        "syria", "syrian", "damascus", "assad",
        "yemen", "yemeni", "houthi", "houthis",
        "iraq", "iraqi", "baghdad",
        "netanyahu", "gallant", "idf", "hamas", "sinwar",
    ],
    "china": [
        "china", "chinese", "beijing", "xi jinping",
        "taiwan", "taiwanese", "taipei",
        "south china sea", "taiwan strait",
    ],
    "latam": [
        "venezuela", "venezuelan", "caracas", "maduro",
        "cuba", "cuban", "havana",
        "mexico", "mexican",
        "colombia", "colombian",
    ],
    "europe": [
        "nato", "european union",
        "uk ", "u.k.", "britain", "british",
        "france", "french", "macron",
        "germany", "german", "scholz",
        "poland", "polish",
    ],
    "africa": [
        "sudan", "sudanese", "khartoum",
        "ethiopia", "ethiopian",
        "somalia", "somalian", "mogadishu",
        "libya", "libyan", "tripoli",
        "nigeria", "nigerian",
    ],
}


def get_cluster(question: str) -> str:
    """
    Assign a geopolitical cluster to a market.
    Returns first matching cluster or "other".
    """
    if not question:
        return "other"
    
    q = question.lower()
    
    # Check clusters in priority order
    for cluster_name, keywords in CLUSTERS.items():
        for kw in keywords:
            if kw in q:
                return cluster_name
    
    return "other"


# =============================================================================
# COMBINED CHECK FOR SNAPSHOT
# =============================================================================

@dataclass
class MarketClassification:
    """Classification result for a market."""
    should_capture: bool      # For snapshot (not garbage)
    is_geopolitical: bool     # For trading (entity + action)
    cluster: str
    capture_reason: str
    
    
def classify_market(question: str) -> MarketClassification:
    """
    Full classification of a market for both snapshot and trading.
    """
    # Check garbage first
    is_junk, junk_reason = is_garbage(question)
    
    if is_junk:
        return MarketClassification(
            should_capture=False,
            is_geopolitical=False,
            cluster="other",
            capture_reason=junk_reason,
        )
    
    # Check geopolitical
    is_geo = is_geopolitical(question)
    cluster = get_cluster(question) if is_geo else "other"
    
    return MarketClassification(
        should_capture=True,
        is_geopolitical=is_geo,
        cluster=cluster,
        capture_reason="geo" if is_geo else "non_geo",
    )


# =============================================================================
# TESTS
# =============================================================================

if __name__ == "__main__":
    test_cases = [
        # Should be CAPTURED + GEO
        ("Will Russia capture Kyiv by March?", True, True, "ukraine"),
        ("US strikes Iran by June 30?", True, True, "mideast"),
        ("Will China invade Taiwan?", True, True, "china"),
        ("Russia x Ukraine ceasefire by March 31?", True, True, "ukraine"),
        ("Netanyahu out as PM by December?", True, True, "mideast"),
        ("Will NATO deploy troops to Ukraine?", True, True, "ukraine"),
        
        # Should be CAPTURED but NOT GEO (no action)
        ("Will Macron visit Beijing?", True, False, "other"),
        ("Iran nuclear deal renewed?", True, True, "mideast"),  # "nuclear" + "iran"
        
        # Should NOT be captured (garbage)
        ("Luka Garza: Rebounds O/U 5.5", False, False, "other"),
        ("Will Georgia Bulldogs win?", False, False, "other"),
        ("Bitcoin price above $100k?", False, False, "other"),
        ("Taylor Swift new album?", False, False, "other"),
        ("Lakers vs Celtics winner?", False, False, "other"),
    ]
    
    print("Testing filters.py:\n")
    passed = 0
    failed = 0
    
    for question, exp_capture, exp_geo, exp_cluster in test_cases:
        result = classify_market(question)
        
        ok = (
            result.should_capture == exp_capture and
            result.is_geopolitical == exp_geo and
            (result.cluster == exp_cluster or exp_cluster == "other")
        )
        
        status = "✅" if ok else "❌"
        if ok:
            passed += 1
        else:
            failed += 1
        
        print(f"{status} '{question[:50]}...'")
        if not ok:
            print(f"   Expected: capture={exp_capture}, geo={exp_geo}, cluster={exp_cluster}")
            print(f"   Got:      capture={result.should_capture}, geo={result.is_geopolitical}, cluster={result.cluster}")
            print(f"   Reason:   {result.capture_reason}")
    
    print(f"\n{passed}/{len(test_cases)} passed")
