"""
POLYMARKET BOT - Configuration
==============================
"""

import os

# =============================================================================
# API CREDENTIALS (from environment variables / GitHub Secrets)
# =============================================================================

# Polymarket API
POLYMARKET_API_KEY = os.getenv("POLYMARKET_API_KEY", "")
POLYMARKET_SECRET = os.getenv("POLYMARKET_SECRET", "")
POLYMARKET_PASSPHRASE = os.getenv("POLYMARKET_PASSPHRASE", "")

# Wallet (for signing transactions)

# Polymarket proxy address (for browser wallet / signature_type=2)
# Find it: polymarket.com → Deposit → Deposit Address

# Telegram notifications (optional)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# =============================================================================
# STRATEGY PARAMETERS
# =============================================================================

# Capital management
BANKROLL = 1500.0  # Total capital in USDC
BET_SIZE = 25.0    # Size per trade in USDC
MIN_CASH_PCT = 0.30  # Switch to "fast recycle" mode below this

# Strategy: NO on 20-60%
BET_SIDE = "NO"
PRICE_YES_MIN = 0.20
PRICE_YES_MAX = 0.60

# Filters
MIN_VOLUME = 10000  # Minimum market volume in USD
BUFFER_HOURS = 48   # Don't trade within 48h of open/close

# Exposure limits
MAX_TOTAL_EXPOSURE_PCT = 0.60   # Max 60% of bankroll exposed
MAX_CLUSTER_EXPOSURE_PCT = 0.20 # Max 20% per geo cluster


# =============================================================================
# LIVE TRADING SETTINGS
# =============================================================================

# Master switch: must be "true" to execute real trades
LIVE_TRADING_ENABLED = os.getenv("LIVE_TRADING_ENABLED", "false").lower() == "true"

# Shadow mode: runs full pipeline but doesn't place orders  
LIVE_SHADOW_MODE = os.getenv("LIVE_SHADOW_MODE", "false").lower() == "true"

# =============================================================================
# KEYWORDS FOR FILTERING (COMPREHENSIVE)
# =============================================================================

# Geopolitical regions with detailed keywords
GEO_REGIONS = {
    # -------------------------------------------------------------------------
    # EASTERN EUROPE / RUSSIA
    # -------------------------------------------------------------------------
    "eastern_europe": {
        "countries": [
            "ukraine", "russia", "belarus", "moldova", "georgia", "armenia", 
            "azerbaijan", "chechnya", "dagestan", "transnistria",
        ],
        "cities": [
            "kyiv", "kiev", "kharkiv", "mariupol", "bakhmut", "kursk", "donetsk",
            "luhansk", "zaporizhzhia", "kherson", "crimea", "sevastopol", "odesa",
            "dnipro", "mykolaiv", "avdiivka", "pokrovsk", "toretsk", "vuhledar",
            "melitopol", "berdiansk", "lysychansk", "sievierodonetsk", "izium",
            "moscow", "minsk", "tbilisi", "yerevan", "baku",
        ],
        "leaders": [
            "putin", "zelensky", "lavrov", "shoigu", "gerasimov", "prigozhin",
            "lukashenko", "medvedev", "kadyrov", "navalny",
        ],
        "orgs": ["wagner", "azov", "fsb", "gru", "roscosmos"],
    },
    
    # -------------------------------------------------------------------------
    # MIDDLE EAST
    # -------------------------------------------------------------------------
    "middle_east": {
        "countries": [
            "israel", "palestine", "gaza", "iran", "iraq", "syria", "lebanon",
            "yemen", "saudi", "jordan", "egypt", "turkey", "qatar", "uae",
            "bahrain", "kuwait", "oman", "libya", "tunisia", "algeria", "morocco",
        ],
        "cities": [
            "tehran", "damascus", "beirut", "rafah", "tel aviv", "jerusalem",
            "west bank", "golan", "sanaa", "aden", "baghdad", "mosul", "aleppo",
            "idlib", "homs", "riyadh", "jeddah", "doha", "dubai", "abu dhabi",
            "cairo", "alexandria", "tripoli", "benghazi", "ankara", "istanbul",
            "gaza city", "khan younis", "jenin", "nablus", "ramallah", "hebron",
        ],
        "leaders": [
            "netanyahu", "khamenei", "raisi", "nasrallah", "sinwar", "haniyeh",
            "erdogan", "assad", "sisi", "mbs", "bin salman", "gallant", "gantz",
            "mohammed bin salman", "abdul malik al-houthi", "ismail haniyeh",
        ],
        "orgs": [
            "hamas", "hezbollah", "houthi", "idf", "irgc", "mossad", "shin bet",
            "pflp", "islamic jihad", "plo", "fatah", "quds force", "kata'ib",
            "popular mobilization", "peshmerga", "sdf", "ypg", "pkk", "isis",
            "al qaeda", "al nusra", "hayat tahrir",
        ],
    },
    
    # -------------------------------------------------------------------------
    # EAST ASIA / PACIFIC
    # -------------------------------------------------------------------------
    "east_asia": {
        "countries": [
            "china", "taiwan", "korea", "north korea", "south korea", "japan",
            "philippines", "vietnam", "indonesia", "malaysia", "singapore",
            "thailand", "myanmar", "burma", "cambodia", "laos", "mongolia",
        ],
        "cities": [
            "beijing", "taipei", "pyongyang", "seoul", "tokyo", "hong kong",
            "shanghai", "manila", "hanoi", "bangkok", "jakarta", "singapore",
            "shenzhen", "guangzhou", "nanjing", "wuhan", "chengdu", "naypyidaw",
        ],
        "leaders": [
            "xi jinping", "kim jong", "kim jong un", "yoon suk yeol", "kishida",
            "marcos", "lai ching-te", "tsai ing-wen", "li qiang", "min aung hlaing",
        ],
        "orgs": ["people's liberation army", "ccp", "kcna"],
        "features": [
            "south china sea", "east china sea", "taiwan strait", "senkaku",
            "diaoyu", "spratly", "paracel", "nine dash", "first island chain",
        ],
    },
    
    # -------------------------------------------------------------------------
    # SOUTH ASIA
    # -------------------------------------------------------------------------
    "south_asia": {
        "countries": [
            "india", "pakistan", "afghanistan", "bangladesh", "sri lanka",
            "nepal", "kashmir", "balochistan",
        ],
        "cities": [
            "new delhi", "islamabad", "kabul", "karachi", "lahore", "mumbai",
            "dhaka", "colombo", "kathmandu", "kandahar", "jalalabad",
        ],
        "leaders": [
            "modi", "sharif", "imran khan", "taliban",
        ],
        "orgs": [
            "taliban", "isis-k", "ttp", "lashkar", "jaish", "pakistan isi",
        ],
    },
    
    # -------------------------------------------------------------------------
    # LATIN AMERICA
    # -------------------------------------------------------------------------
    "latin_america": {
        "countries": [
            "venezuela", "brazil", "mexico", "colombia", "argentina", "chile",
            "peru", "ecuador", "bolivia", "cuba", "nicaragua", "el salvador",
            "guatemala", "honduras", "haiti", "dominican", "panama", "paraguay",
            "uruguay", "guyana", "suriname",
        ],
        "cities": [
            "caracas", "brasilia", "mexico city", "bogota", "buenos aires",
            "santiago", "lima", "quito", "la paz", "havana", "managua",
            "san salvador", "guatemala city", "tegucigalpa", "port-au-prince",
        ],
        "leaders": [
            "maduro", "lula", "amlo", "obrador", "petro", "milei", "boric",
            "bukele", "ortega", "diaz-canel", "guaido",
        ],
        "orgs": [
            "farc", "eln", "cartel", "sinaloa", "cjng", "jalisco",
        ],
    },
    
    # -------------------------------------------------------------------------
    # AFRICA
    # -------------------------------------------------------------------------
    "africa": {
        "countries": [
            "sudan", "south sudan", "ethiopia", "eritrea", "somalia", "kenya",
            "nigeria", "niger", "mali", "burkina faso", "chad", "cameroon",
            "congo", "drc", "rwanda", "uganda", "tanzania", "mozambique",
            "zimbabwe", "south africa", "angola", "namibia", "botswana",
            "senegal", "ivory coast", "ghana", "guinea", "liberia", "sierra leone",
            "central african republic",
        ],
        "cities": [
            "khartoum", "addis ababa", "mogadishu", "nairobi", "lagos", "abuja",
            "niamey", "bamako", "ouagadougou", "ndjamena", "kinshasa", "kampala",
            "pretoria", "johannesburg", "cape town", "luanda", "harare", "dakar",
        ],
        "leaders": [
            "al-burhan", "hemeti", "abiy ahmed", "kagame", "museveni", "tshisekedi",
        ],
        "orgs": [
            "rsf", "rapid support forces", "al shabaab", "boko haram", "jnim",
            "isis sahel", "m23", "adf", "wagner africa",
        ],
    },
    
    # -------------------------------------------------------------------------
    # EUROPE / EU / NATO
    # -------------------------------------------------------------------------
    "europe": {
        "entities": [
            "european union", "nato", "brexit", "schengen",  # Removed "eu" - too short, matches "ethereum"
        ],
        "countries": [
            "germany", "france", "uk", "united kingdom", "britain", "england",
            "poland", "romania", "hungary", "czech", "slovakia", "austria",
            "italy", "spain", "portugal", "greece", "bulgaria", "serbia",
            "croatia", "slovenia", "bosnia", "kosovo", "albania", "montenegro",
            "north macedonia", "finland", "sweden", "norway", "denmark",
            "netherlands", "belgium", "luxembourg", "ireland", "scotland",
            "estonia", "latvia", "lithuania", "cyprus", "malta", "iceland",
            "switzerland",
        ],
        "cities": [
            "brussels", "berlin", "paris", "london", "warsaw", "budapest",
            "prague", "vienna", "rome", "madrid", "athens", "bucharest",
            "belgrade", "zagreb", "sarajevo", "pristina", "tirana", "skopje",
            "helsinki", "stockholm", "oslo", "copenhagen", "amsterdam",
            "dublin", "lisbon", "geneva", "zurich",
        ],
        "leaders": [
            "macron", "scholz", "starmer", "sunak", "meloni", "orban", "duda",
            "von der leyen", "stoltenberg", "rutte", "draghi", "sanchez", "tusk",
        ],
    },
    
    # -------------------------------------------------------------------------
    # INTERNATIONAL / GLOBAL
    # -------------------------------------------------------------------------
    "international": {
        "orgs": [
            "nato", "united nations", "iaea", "icj", "icc", "who",  # Removed "un" - too short
            "imf", "world bank", "wto", "opec", "brics", "g7", "g20",
            "security council", "general assembly", "african union", "asean",
            "arab league", "gcc", "osce", "interpol",
        ],
        "concepts": [
            "sanctions", "embargo", "treaty", "accord", "resolution",
            "peacekeeping", "humanitarian", "refugee", "asylum",
            "war crime", "genocide", "ethnic cleansing", "crimes against humanity",
        ],
    },
}

# Action keywords (confirms geopolitical context)
ACTION_KEYWORDS = [
    # Military operations
    "invasion", "incursion", "offensive", "counter-offensive", "counteroffensive",
    "airstrike", "air strike", "missile", "strike", "attack", "bomb", "bombing",
    "drone", "uav", "artillery", "shelling", "raid", "ambush", "assault",
    "capture", "seize", "liberate", "advance", "retreat", "encircle", "siege",
    "occupy", "annex", "mobilization", "conscription", "deployment",
    "frontline", "front line", "battlefield",
    
    # Naval/Maritime
    "blockade", "naval", "warship", "submarine", "carrier", "fleet",
    
    # Aerial
    "no-fly zone", "air defense", "interceptor", "fighter jet", "bomber",
    
    # Weapons
    "tank", "armored", "infantry", "troops", "soldiers", "battalion", "brigade",
    "missile defense", "patriot", "himars", "javelin", "leopard", "abrams",
    "f-16", "f-35", "s-300", "s-400", "icbm", "hypersonic", "cruise missile",
    
    # WMD/Escalation
    "nuclear", "atomic", "wmd", "chemical", "biological", "dirty bomb",
    "enrichment", "uranium", "plutonium", "warhead", "escalation", "deterrent",
    
    # Diplomacy
    "ceasefire", "cease-fire", "truce", "armistice", "peace", "treaty",
    "negotiate", "negotiation", "talks", "summit", "agreement", "deal",
    "diplomatic", "diplomacy", "envoy", "ambassador", "mediation",
    
    # Sanctions/Economic warfare
    "sanction", "embargo", "tariff", "trade war", "economic warfare",
    "asset freeze", "swift", "export control",
    
    # Crisis
    "coup", "uprising", "revolution", "revolt", "insurgency", "rebellion",
    "civil war", "regime change", "martial law", "state of emergency",
    "assassination", "assassinate", "killing", "execute", "execution",
    
    # Humanitarian
    "hostage", "prisoner", "pow", "detainee", "kidnap", "abduct",
    "refugee", "displaced", "evacuation", "humanitarian", "aid convoy",
    "war crime", "atrocity", "massacre", "genocide",
    
    # Intelligence
    "espionage", "spy", "intelligence", "cyber attack", "cyberattack", "hack",
    "sabotage", "disinformation", "propaganda",
]

# Build flat GEO_KEYWORDS list from regions (WITHOUT action keywords)
def _build_geo_keywords():
    keywords = set()
    for region_data in GEO_REGIONS.values():
        for key, values in region_data.items():
            if isinstance(values, list):
                keywords.update(v.lower() for v in values)
    # NOTE: We do NOT add ACTION_KEYWORDS here anymore
    # Action keywords alone should not qualify a market as geopolitical
    return list(keywords)

GEO_KEYWORDS = _build_geo_keywords()

# =============================================================================
# EXCLUSION KEYWORDS (comprehensive)
# =============================================================================

EXCLUDE_KEYWORDS = [
    # -------------------------------------------------------------------------
    # GAMING / ESPORTS
    # -------------------------------------------------------------------------
    "counter-strike", "cs2", "csgo", "valorant", "league of legends", "lol",
    "dota", "overwatch", "fortnite", "call of duty", "cod", "apex legends",
    "pubg", "rainbow six", "r6", "rocket league", "fifa", "madden", "2k",
    "esports", "esport", "e-sports", "gaming", "twitch", "streamer",
    "speedrun", "gamer", "playstation", "xbox", "nintendo", "steam",
    "world of warcraft", "wow", "minecraft", "roblox", "genshin",
    
    # -------------------------------------------------------------------------
    # TRADITIONAL SPORTS
    # -------------------------------------------------------------------------
    # American sports
    "nfl", "nba", "mlb", "nhl", "mls", "super bowl", "world series",
    "stanley cup", "march madness", "ncaa", "college football", "college basketball",
    "touchdown", "quarterback", "three pointer", "home run", "playoff",
    
    # Football/Soccer
    "premier league", "la liga", "serie a", "bundesliga", "ligue 1",
    "champions league", "europa league", "world cup", "euro 2024", "euro 2028",
    "copa america", "messi", "ronaldo", "mbappe", "haaland", "goalkeeper",
    
    # Combat sports
    "ufc", "mma", "boxing", "bellator", "pfl", "one championship",
    "heavyweight", "lightweight", "middleweight", "knockout", "ko", "tko",
    "submission", "wrestling", "wwe", "aew",
    
    # Other sports
    "tennis", "wimbledon", "us open", "french open", "australian open",
    "golf", "pga", "masters", "british open", "ryder cup",
    "f1", "formula 1", "formula one", "nascar", "indycar", "motogp",
    "cricket", "ipl", "ashes", "t20",
    "olympics", "olympic", "paralympic",
    "rugby", "six nations",
    "cycling", "tour de france",
    "horse racing", "kentucky derby", "grand national",
    "skiing", "snowboard", "surfing", "skateboard",
    "baseball", "basketball", "football", "hockey", "soccer",
    
    # -------------------------------------------------------------------------
    # ENTERTAINMENT / CELEBRITIES
    # -------------------------------------------------------------------------
    # Awards
    "grammy", "oscar", "emmy", "tony", "golden globe", "bafta", "mtv",
    "academy award", "billboard", "brit award", "american music",
    
    # Streaming/Media
    "netflix", "disney+", "hbo", "amazon prime", "hulu", "paramount+",
    "apple tv", "peacock", "spotify", "youtube", "tiktok",
    "movie", "film", "cinema", "box office", "sequel", "franchise",
    "tv show", "series", "episode", "season", "finale", "premiere",
    "documentary", "reality tv", "talk show",
    
    # Music
    "album", "single", "concert", "tour", "festival", "coachella",
    "glastonbury", "lollapalooza", "grammy", "billboard hot",
    "taylor swift", "drake", "beyonce", "kanye", "ye", "travis scott",
    "bts", "blackpink", "kpop", "k-pop",
    
    # Celebrities (non-political)
    "kardashian", "jenner", "bieber", "selena gomez", "ariana grande",
    "dua lipa", "harry styles", "ed sheeran", "adele", "rihanna",
    "tom cruise", "leonardo dicaprio", "brad pitt", "angelina jolie",
    "johnny depp", "amber heard", "will smith", "chris rock",
    
    # -------------------------------------------------------------------------
    # CRYPTO / FINANCE (prices, not geopolitics)
    # -------------------------------------------------------------------------
    "bitcoin price", "btc price", "ethereum price", "eth price",
    "ethereum", "bitcoin",  # Added - too many false positives
    "solana price", "sol price", "crypto price", "token price",
    "doge", "dogecoin", "shiba", "memecoin", "meme coin",
    "nft", "airdrop", "defi", "yield", "staking", "mining",
    "altcoin", "market cap", "ath", "all time high",
    "bull run", "bear market", "pump", "dump", "moon",
    "fdv", "token launch", "tge",  # Added - crypto token launches
    
    # Stock specific
    "stock price", "share price", "earnings", "quarterly",
    "ipo", "spac", "dividend", "buyback", "market open", "market close",
    "dow jones", "s&p 500", "nasdaq", "nyse", "ftse", "dax",
    
    # -------------------------------------------------------------------------
    # TECH (non-geopolitical)
    # -------------------------------------------------------------------------
    "iphone", "android", "samsung", "pixel", "macbook", "windows",
    "app store", "play store", "software update", "bug fix", "feature",
    "ai model", "chatgpt", "gpt-5", "claude", "gemini", "llama",
    "startup", "unicorn", "vc", "funding round", "series a",
    "product launch", "wwdc", "google io", "keynote",
    "tesla", "full self driving", "fsd", "autopilot",  # Added Tesla
    
    # -------------------------------------------------------------------------
    # NATURAL DISASTERS (not geopolitics unless conflict-related)
    # -------------------------------------------------------------------------
    "earthquake", "magnitude", "richter", "tsunami", "volcano",
    "hurricane", "typhoon", "cyclone", "tornado", "wildfire",
    
    # -------------------------------------------------------------------------
    # HEALTH (non-geopolitical)
    # -------------------------------------------------------------------------
    "heart attack", "stroke", "cancer", "diagnosis", "surgery",
    "hospital", "medical", "doctor", "vaccine", "fda approval",
    "clinical trial", "drug approval", "pharmaceutical",
    "weight loss", "ozempic", "diet", "fitness",
    "mental health", "depression", "anxiety", "therapy",
    
    # -------------------------------------------------------------------------
    # WEATHER (unless disaster)
    # -------------------------------------------------------------------------
    "temperature", "forecast", "sunny", "rainy", "snow day",
    "heat wave", "cold snap", "pollen", "allergy",
    
    # -------------------------------------------------------------------------
    # MISC / LIFESTYLE
    # -------------------------------------------------------------------------
    "wedding", "divorce", "baby", "pregnant", "birthday", "anniversary",
    "dating", "relationship", "breakup", "engagement",
    "fashion", "runway", "vogue", "met gala",
    "restaurant", "michelin", "food", "recipe",
    "real estate", "housing market", "mortgage rate",
    "travel", "vacation", "tourism", "airline",
    "lottery", "powerball", "mega millions", "jackpot",
    "super bowl ad", "commercial", "advertisement",
    
    # -------------------------------------------------------------------------
    # FALSE POSITIVES (words that look geo but aren't)
    # -------------------------------------------------------------------------
    "georgia bulldogs", "georgia tech", "miami heat", "miami dolphins",
    "houston rockets", "phoenix suns", "golden state warriors",
    "washington commanders", "washington wizards", "washington nationals",
    "new york giants", "new york jets", "new york knicks", "new york yankees",
    "los angeles rams", "los angeles lakers", "los angeles dodgers",
    "paris saint-germain", "psg", "bayern munich", "manchester united",
    "manchester city", "liverpool fc", "arsenal fc", "chelsea fc",
    "juventus", "barcelona", "real madrid", "inter milan", "ac milan",
    
    # -------------------------------------------------------------------------
    # ADDITIONAL FALSE POSITIVES (identified from paper trading)
    # -------------------------------------------------------------------------
    # Sports - specific patterns
    "both teams to score", "wins the toss", "odi:", "vs.", 
    "patriots", "championship round", "semi-final", "semifinals",
    "internazionale", "borussia", "dortmund",
    
    # Eurovision
    "eurovision",
    
    # Stunts/Records
    "free solo", "honnold", "taipei 101",
    
    # Central banks / Monetary policy
    "interest rate", "key rate", "bps", "bank of japan", "bank of mexico",
    "bank of russia", "unemployment rate", "decrease the key", "increase the key",
    
    # Fed (monetary, not geopolitical)
    "jerome powell", "fed board", "fed nominee",
    
    # Memes / Gaming references
    "gta vi", "before gta", "nothing ever happens",
]

# =============================================================================
# CLUSTERS FOR EXPOSURE LIMITS
# =============================================================================

CLUSTERS = {
    "ukraine": [
        "ukraine", "russia", "kyiv", "kiev", "donbas", "crimea", "kherson",
        "bakhmut", "kursk", "zaporizhzhia", "donetsk", "luhansk", "kharkiv",
        "mariupol", "odesa", "putin", "zelensky", "wagner", "azov",
        "avdiivka", "pokrovsk", "toretsk", "melitopol",
    ],
    "mideast": [
        "israel", "gaza", "palestine", "iran", "hezbollah", "hamas", 
        "lebanon", "yemen", "houthi", "rafah", "netanyahu", "idf",
        "tehran", "khamenei", "sinwar", "nasrallah", "west bank",
        "syria", "assad", "iraq", "irgc", "quds",
    ],
    "china": [
        "china", "taiwan", "beijing", "xi jinping", "south china sea",
        "taipei", "pla", "taiwan strait", "ccp",
    ],
    "latam": [
        "venezuela", "maduro", "guaido", "caracas", "colombia", "petro",
        "brazil", "lula", "mexico", "amlo", "cuba", "nicaragua", "ortega",
        "argentina", "milei", "bukele", "el salvador",
    ],
    "europe": [
        "nato", "eu", "european union", "brussels", "macron", "scholz",
        "france", "germany", "poland", "hungary", "orban", "stoltenberg",
        "finland", "sweden",
    ],
    "africa": [
        "sudan", "ethiopia", "somalia", "nigeria", "niger", "mali",
        "burkina", "chad", "congo", "drc", "wagner africa", "rsf",
        "al shabaab", "boko haram", "sahel",
    ],
}

# =============================================================================
# API ENDPOINTS
# =============================================================================

GAMMA_API_URL = "https://gamma-api.polymarket.com"
CLOB_API_URL = "https://clob.polymarket.com"

# =============================================================================
# OPERATIONAL
# =============================================================================

DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"  # Set to False to execute real trades
LOG_FILE = "bot_history.json"

# Paper trading settings
PAPER_ENTRY_COST_RATE = 0.03  # 3% simulated spread + slippage

# Backward compatible aliases (some modules expect these names)
ENTRY_COST_RATE = PAPER_ENTRY_COST_RATE  # alias
EXIT_COST_RATE = 0.03  # default exit cost rate (paper trading)
