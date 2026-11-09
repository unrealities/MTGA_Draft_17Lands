import os

# --- PATHS ---
OUTPUT_DIR = os.getenv(
    "ETL_OUTPUT_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "build")
)

# --- API ETIQUETTE & CONFIG ---
USER_AGENT = "MTGADraftTool-ETL/2.1 (https://github.com/unrealities/MTGA_Draft_17Lands)"
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json",
    "Accept-Encoding": "gzip, deflate",
}

# Delays explicitly requested by community API guidelines
DELAY_17LANDS_SEC = 6.0
DELAY_SCRYFALL_SEC = 0.2

# Reliability & Anti-Bot config
REQUEST_TIMEOUT_SEC = int(os.getenv("ETL_TIMEOUT", 30))
MAX_ATTEMPTS = 4
RETRY_BASE_DELAY_SEC = 5.0
WAF_COOLDOWN_SEC = 180.0  # 3 minutes of sleep if we get a 403/WAF block

# Statistical Thresholds
MIN_GAMES_THRESHOLD = 500  # Increased to reduce API spam and filter out noisy data

# --- 17LANDS TIME PERIODS ---
# 17Lands dropped custom start_date/end_date ranges in favour of these preset
# "time_period" values (the drop-down on the card pages). These strings are the
# query values sent by the site; confirm against the browser Network tab if a
# preset ever stops returning data.
TIME_PERIOD_ALL_TIME = "ALL_TIME"
TIME_PERIOD_ALL_EXCEPT_FIRST_WEEK = "ALL_EXCEPT_FIRST_WEEK"
TIME_PERIOD_LATEST_EVENT = "LATEST_EVENT"
TIME_PERIOD_LAST_TWO_WEEKS = "LAST_TWO_WEEKS"
TIME_PERIOD_LAST_WEEK = "LAST_WEEK"
TIME_PERIOD_LAST_DAY = "LAST_DAY"
TIME_PERIOD_FIRST_WEEK = "FIRST_WEEK"


def default_time_period(set_code: str) -> str:
    """The ETL pulls full history for standard sets, but Cube runs are distinct
    short-lived events, so we take the latest event to avoid blending them."""
    if "CUBE" in set_code.upper():
        return TIME_PERIOD_LATEST_EVENT
    return TIME_PERIOD_ALL_TIME


# Data-quality validation. A brand-new set can legitimately look thin on day
# one/two (few games, sparse archetypes), so validation only *blocks* a publish
# once the set has at least this many days of data. Below that, issues are logged
# but the dataset is still published.
VALIDATION_ENFORCE_MIN_DAYS = 3

# --- DATA TARGETS ---
ARCHETYPES = [
    "All Decks",
    "W",
    "U",
    "B",
    "R",
    "G",  # Mono
    "WU",
    "UB",
    "BR",
    "RG",
    "WG",
    "WB",
    "UR",
    "BG",
    "WR",
    "UG",  # Guilds
    "WUB",
    "UBR",
    "BRG",
    "WRG",
    "WUG",
    "WBR",
    "URG",
    "WBG",
    "WUR",
    "UBG",  # 3-Color
    "WUBR",
    "UBRG",
    "WBRG",
    "WURG",
    "WUBG",
    "WUBRG",  # 4 & 5-Color
]

O_TAGS = {
    "removal": "otag:removal OR otag:board-wipe OR otag:burn OR otag:counterspell OR otag:pacifism OR otag:edict OR otag:destroy OR otag:exile",
    "fixing_ramp": "otag:mana-fixing OR otag:fetchland OR otag:mana-dork OR otag:treasure OR otag:ramp OR otag:mana-rock",
    "card_advantage": "otag:card-draw OR otag:card-selection OR otag:recursion OR otag:tutor OR otag:cantrip OR kw:investigate OR kw:surveil",
    "evasion": "otag:evasion OR kw:flying OR kw:menace OR kw:trample OR kw:unblockable OR kw:skulk OR kw:shadow",
    "combat_trick": "otag:combat-trick OR otag:pump-spell OR otag:protection-spell",
    "mana_sink": "otag:mana-sink OR kw:kicker OR kw:multikicker OR kw:adapt",
    "token_maker": "otag:token-generator OR kw:amass OR kw:incubate",
    "lifegain": "otag:lifegain OR kw:lifelink",
    "protection": "otag:hexproof-granter OR otag:indestructible-granter OR otag:blink OR otag:flicker OR otag:ward-granter",
    "hate": "otag:graveyard-hate OR otag:artifact-destruction OR otag:enchantment-destruction",
}
