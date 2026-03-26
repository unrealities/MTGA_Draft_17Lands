import os

# --- PATHS ---
# Allows CI/CD pipelines (like GitHub Actions) to define where the build goes
OUTPUT_DIR = os.getenv(
    "ETL_OUTPUT_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "build")
)

# --- API ETIQUETTE & CONFIG ---
USER_AGENT = "MTGADraftTool-ETL/2.0 (https://github.com/unrealities/MTGA_Draft_17Lands)"
HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}

# Delays explicitly requested by community API guidelines
DELAY_17LANDS_SEC = 3.0
DELAY_SCRYFALL_SEC = 0.2

# Reliability config
REQUEST_TIMEOUT_SEC = int(os.getenv("ETL_TIMEOUT", 30))
MAX_ATTEMPTS = 4
RETRY_BASE_DELAY_SEC = 5.0

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
    "synergy_artifacts": "otag:artifact-synergy OR otag:cares-about-artifacts",
    "synergy_graveyard": "otag:graveyard-synergy OR otag:cares-about-graveyard",
    "synergy_counters": "otag:counters-synergy OR otag:cares-about-counters",
}
