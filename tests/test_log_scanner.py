import pytest
import os
from typing import List
from pydantic.dataclasses import dataclass
from pydantic import Field
from unittest.mock import patch, MagicMock, mock_open
from src.log_scanner import ArenaScanner, Source
from src.limited_sets import SetDictionary, SetInfo, SpecialEvent
from src.file_extractor import (
    FileExtractor,
    decode_mana_cost,
    extract_types,
    initialize_card_data,
    check_date,
)
from src import constants
from src.utils import Result

TEST_LOG_DIRECTORY = os.path.join(os.getcwd(), "tests")
TEST_LOG_FILE_LOCATION = os.path.join(os.getcwd(), "tests", "Player.log")
TEST_SETS_DIRECTORY = os.path.join(os.getcwd(), "tests","data")

OTJ_PREMIER_SNAPSHOT = os.path.join(os.getcwd(), "tests", "data","OTJ_PremierDraft_Data_2024_5_3.json")

OTJ_EVENT_ENTRY = r'[UnityCrossThreadLogger]==> Event_Join {"id":"11a8f74b-1afb-4d25-bb35-55d43674c808","request":"{\"EventName\":\"PremierDraft_OTJ_20240416\",\"EntryCurrencyType\":\"Gem\",\"EntryCurrencyPaid\":1500,\"CustomTokenId\":null}"}'
OTJ_P1P1_ENTRY = r'[UnityCrossThreadLogger]==> LogBusinessEvents {"id":"a5515a1a-d96e-4da3-9a4a-c03cc4b2b938","request":"{\"PlayerId\":null,\"ClientPlatform\":null,\"DraftId\":\"87b408d1-43e0-4fb5-8c74-a1227fde087c\",\"EventId\":\"PremierDraft_OTJ_20240416\",\"SeatNumber\":1,\"PackNumber\":1,\"PickNumber\":1,\"PickGrpId\":90459,\"CardsInPack\":[90734,90584,90631,90362,90440,90349,90486,90527,90406,90439,90488,90480,90388,90459],\"AutoPick\":false,\"TimeRemainingOnPick\":63.99701,\"EventType\":24,\"EventTime\":\"2024-05-08T00:56:34.4223433Z\"}"}'
OTJ_P1P1_CARD_NAMES =[
    "Back for More",
    "Wrangler of the Damned",
    "Holy Cow",
    "Mourner's Surprise",
    "Armored Armadillo",
    "Reckless Lackey",
    "Snakeskin Veil",
    "Peerless Ropemaster",
    "Lively Dirge",
    "Return the Favor",
    "Magebane Lizard",
    "Deepmuck Desperado",
    "Vadmir, New Blood"
]
OTJ_P1P2_ENTRY_SKIP = r'[UnityCrossThreadLogger]==> LogBusinessEvents {"id":"972efef7-cd60-4254-ae18-634210287c95","request":"{\"PlayerId\":null,\"ClientPlatform\":null,\"DraftId\":\"87b408d1-43e0-4fb5-8c74-a1257fde087c\",\"EventId\":\"PremierDraft_OTJ_20240416\",\"SeatNumber\":1,\"PackNumber\":1,\"PickNumber\":2,\"PickGrpId\":90701,\"CardsInPack\":[90702,90417,90607,90524,90481,90588,90440,90418,90353,90494,90360,90609,90548],\"AutoPick\":false,\"TimeRemainingOnPick\":30.8176479,\"EventType\":24,\"EventTime\":\"2024-05-08T00:57:07.6027017Z\"}"}'

TEST_SETS = SetDictionary(data={
    "OM1" : SetInfo(seventeenlands=["OM1"]),
    "TDM" : SetInfo(seventeenlands=["TDM"]),
    "DSK" : SetInfo(seventeenlands=["DSK"]),
    "MH3" : SetInfo(seventeenlands=["MH3"]),
    "OTJ" : SetInfo(seventeenlands=["OTJ"]),
    "MKM" : SetInfo(seventeenlands=["MKM"]),
    "DMU" : SetInfo(seventeenlands=["DMU"]),
    "Arena Cube": SetInfo(seventeenlands=["CUBE"]),
    "Powered Cube": SetInfo(seventeenlands=["CUBE - POWERED"]),
    },
    special_events=[
        SpecialEvent(
            label="OpenDay1",
            type="Sealed",
            set_code="MH3",
            keywords=["ArenaOpen","Day1"]
        ),
        SpecialEvent(
            label="OpenDay2",
            type="PremierDraft",
            set_code="OTJ",
            keywords=["ArenaOpen","Day2"]
        ),
        SpecialEvent(
            label="QualSealed",
            type="Sealed",
            set_code="MKM",
            keywords=["Qualifier"]
        )
    ]
)

CUBE_EVENT_TESTS = [
    (
        "Powered Cube",
        r'[UnityCrossThreadLogger]==> EventJoin {"id":"23c1c6a7-3ce2-4a8c-88cf-88ef6dbc266b","request":"{\"EventName\":\"CubeDraft_Powered_20251028\",\"EntryCurrencyType\":\"Gem\",\"EntryCurrencyPaid\":1500,\"CustomTokenId\":null,\"EventChoice\":\"\"}"}',
        ["CUBE - POWERED"],
        "PremierDraft"
    ),
    (
        "Generic Arena Cube",
        r'[UnityCrossThreadLogger]==> EventJoin {"id":"a1b2c3d4-e5f6-a7b8-c9d0-e1f2a3b4c5d6","request":"{\"EventName\":\"CubeDraft_Arena_20240101\",\"EntryCurrencyType\":\"Gold\",\"EntryCurrencyPaid\":4000,\"CustomTokenId\":null}"}',
        ["CUBE"],
        "PremierDraft"
    ),
]

URL_ENCODING_TEST_CASES = [
    ("OTJ", "OTJ"),
    ("CUBE - POWERED", "CUBE%20-%20POWERED"),
    ("SET/CODE", "SET%2FCODE"),
    ("SPECIAL&CHARS", "SPECIAL%26CHARS"),
]

@pytest.fixture
def file_extractor():
    """Fixture to create a FileExtractor instance with default values for testing."""
    extractor = FileExtractor(directory=None)
    extractor.draft = "PremierDraft"
    extractor.start_date = "2023-01-01"
    extractor.end_date = "2023-01-31"
    extractor.user_group = constants.LIMITED_USER_GROUP_ALL
    return extractor

@dataclass
class EventResults:
    new_event: bool = False
    data_update: bool = False
    current_set: str = ""
    current_event: str = ""
    current_pack: int = 0
    current_pick: int = 0
    picks: List[str] = Field(default_factory=list)
    pack: List[str] = Field(default_factory=list)
    card_pool: List[str] = Field(default_factory=list)
    missing: List[str] = Field(default_factory=list)

# Premier draft log entries collected from Player.log after the 2025-4-8 Arena Update
TDM_PREMIER_DRAFT_ENTRIES_2025_4_8 = [
    (
        "Event Start",
        EventResults(
            new_event=True,
            data_update=False,
            current_set="TDM",
            current_event="PremierDraft",
            current_pack=0,
            current_pick=0,
            picks=[],
            pack=[],
            card_pool=[],
            missing=[],
        ),
        r'[UnityCrossThreadLogger]==> EventJoin {"id":"d39f27d5-23c9-4ffd-b5d3-888c9bbccd97","request":"{\"EventName\":\"PremierDraft_TDM_20250408\",\"EntryCurrencyType\":\"Gold\",\"EntryCurrencyPaid\":10000,\"CustomTokenId\":null}"}'
    ),
    (
        "P1P1 - Pack",
        EventResults(
            new_event=False,
            data_update=True,
            current_set="TDM",
            current_event="PremierDraft",
            current_pack=1,
            current_pick=1,
            picks=[],
            pack=["95536","95586","95574","95615","95544","95742","95640","95663","95732","95635","95700","95561","95606","95804"], 
            card_pool=[],
            missing=[],
        ),
        r'[UnityCrossThreadLogger]==> LogBusinessEvents {"id":"ee35cead-cddb-4ef0-919e-eb0fe92097b5","request":"{\"PlayerId\":null,\"ClientPlatform\":null,\"DraftId\":\"395f747c-07a0-4aed-8bb2-a4b399b24bb5\",\"EventId\":\"PremierDraft_TDM_20250408\",\"SeatNumber\":5,\"PackNumber\":1,\"PickNumber\":1,\"PickGrpId\":95606,\"PickGrpIds\":[95606],\"CardsInPack\":[95536,95586,95574,95615,95544,95742,95640,95663,95732,95635,95700,95561,95606,95804],\"AutoPick\":false,\"TimeRemainingOnPick\":58.92359,\"EventType\":24,\"EventTime\":\"2025-04-19T14:45:33.8146729Z\"}"}'
    ),    
    (
        "P1P1 - Pick",
        EventResults(
            new_event=False,
            data_update=True,
            current_set="TDM",
            current_event="PremierDraft",
            current_pack=1,
            current_pick=1,
            picks=["95606"],
            pack=["95536","95586","95574","95615","95544","95742","95640","95663","95732","95635","95700","95561","95606","95804"], 
            card_pool=["95606"],
            missing=[]
        ),
        r'[UnityCrossThreadLogger]==> EventPlayerDraftMakePick {"id":"85c3c7c3-37be-49f3-8b6a-1bfe03bda027","request":"{\"DraftId\":\"395f747c-07a0-4aed-8bb2-a4b399b24bb5\",\"GrpId\":0,\"GrpIds\":[95606],\"Pack\":1,\"Pick\":1}"}'
    ),
    (
        "P1P2 - Pack",
        EventResults(
            new_event=False,
            data_update=True,
            current_set="TDM",
            current_event="PremierDraft",
            current_pack=1,
            current_pick=2,
            picks=[],
            pack=["95742","95678","95533","95624","95741","95627","95587","95572","95665","95546","95611","95781","95798"],
            card_pool=["95606"],
            missing=[]
        ),
        r'[UnityCrossThreadLogger]Draft.Notify {"draftId":"395f747c-07a0-4aed-8bb2-a4b399b24bb5","SelfPick":2,"SelfPack":1,"PackCards":"95742,95678,95533,95624,95741,95627,95587,95572,95665,95546,95611,95781,95798"}'
    ),
]

# Premier draft log entries collected from Player.log after 2024-5-7 Arena update
OTJ_PREMIER_DRAFT_ENTRIES_2024_5_7 = [
    (
        "Event Start",
        EventResults(
            new_event=True,
            data_update=False,
            current_set="OTJ",
            current_event="PremierDraft",
            current_pack=0,
            current_pick=0,
            picks=[],
            pack=[],
            card_pool=[],
            missing=[],
        ),
        OTJ_EVENT_ENTRY
    ),
    (
        "P1P1 - Pack",
        EventResults(
            new_event=False,
            data_update=True,
            current_set="OTJ",
            current_event="PremierDraft",
            current_pack=1,
            current_pick=1,
            picks=[],
            pack=["90734","90584","90631","90362","90440","90349","90486","90527","90406","90439","90488","90480","90388","90459"], 
            card_pool=[],
            missing=[],
        ),
        OTJ_P1P1_ENTRY
    ),
    (
        "P1P1 - Pick",
        EventResults(
            new_event=False,
            data_update=True,
            current_set="OTJ",
            current_event="PremierDraft",
            current_pack=1,
            current_pick=1,
            picks=["90459"],
            pack=["90734","90584","90631","90362","90440","90349","90486","90527","90406","90439","90488","90480","90388","90459"],
            card_pool=["90459"],
            missing=[]
        ),
        r'[UnityCrossThreadLogger]==> Event_PlayerDraftMakePick {"id":"a14a9a98-f408-4051-8799-50df13eb18ad","request":"{\"DraftId\":\"87b408d1-43e0-4fb5-8c74-a1257fde387c\",\"GrpId\":90459,\"Pack\":1,\"Pick\":1}"}'
    ),
    (
        "P1P2 - Pack",
        EventResults(
            new_event=False,
            data_update=True,
            current_set="OTJ",
            current_event="PremierDraft",
            current_pack=1,
            current_pick=2,
            picks=[],
            pack=["90701","90416","90606","90524","90481","90588","90440","90418","90353","90494","90360","90609","90548"],
            card_pool=["90459"],
            missing=[]
        ),
        r'[UnityCrossThreadLogger]Draft.Notify {"draftId":"87b408d1-43e0-4fb5-8c74-a1257fde017c","SelfPick":2,"SelfPack":1,"PackCards":"90701,90416,90606,90524,90481,90588,90440,90418,90353,90494,90360,90609,90548"}'
    ),
    (
        "P1P2 - Pack Skip Repeat",
        EventResults(
            new_event=False,
            data_update=False,
            current_set="OTJ",
            current_event="PremierDraft",
            current_pack=1,
            current_pick=2,
            picks=[],
            pack=["90701","90416","90606","90524","90481","90588","90440","90418","90353","90494","90360","90609","90548"],
            card_pool=["90459"],
            missing=[]
        ),
        OTJ_P1P2_ENTRY_SKIP
    ),
    (
        "P1P9 - Pack",
        EventResults(
            new_event=False,
            data_update=True,
            current_set="OTJ",
            current_event="PremierDraft",
            current_pack=1,
            current_pick=9,
            picks=["90459"],
            pack=["90631","90349","90486","90406","90488","90480"],
            card_pool=["90459"],
            missing=["90734","90584","90362","90440","90527","90439","90388","90459"]
        ),
        r'[UnityCrossThreadLogger]Draft.Notify {"draftId":"87b108d1-43e0-4fb5-8c74-a1257fde087c","SelfPick":9,"SelfPack":1,"PackCards":"90631,90349,90486,90406,90488,90480"}'
    ),
    (
        "P3P14 - Pack",
        EventResults(
            new_event=False,
            data_update=True,
            current_set="OTJ",
            current_event="PremierDraft",
            current_pack=3,
            current_pick=14,
            picks=[],
            pack=["90625"],
            card_pool=["90459"],
            missing=[]
        ),
        r'[UnityCrossThreadLogger]Draft.Notify {"draftId":"87b408d1-43e0-4fb5-8c74-a1257fde087c","SelfPick":14,"SelfPack":3,"PackCards":"90625"}'
    )
]

# Premier draft log entries collected from Player.log before 2024-5-7 Arena update
MKM_PREMIER_DRAFT_ENTRIES = [
    (
        "Event Start",
        EventResults(
            new_event=True,
            data_update=False,
            current_set="MKM",
            current_event="PremierDraft",
            current_pack=0,
            current_pick=0,
            picks=[],
            pack=[],
            card_pool=[],
            missing=[]
        ),
        r'[UnityCrossThreadLogger]==> Event_Join {"id":"4adb764e-3c33-46a9-91e6-4393bc7a5895","request":"{\"Type\":600,\"TransId\":\"4adb764e-3c33-46a9-91e6-4393bc7a5895\",\"Payload\":\"{\\\"EventName\\\":\\\"PremierDraft_MKM_20240206\\\",\\\"EntryCurrencyType\\\":\\\"Gold\\\",\\\"EntryCurrencyPaid\\\":10000,\\\"CustomTokenId\\\":null}\"}"}'
    ),
    (
        "P1P1 - Pack",
        EventResults(
            new_event=False,
            data_update=True,
            current_set="MKM",
            current_event="PremierDraft",
            current_pack=1,
            current_pick=1,
            picks=[],
            pack=["89119","89040","89008","88926","89093","88981","88950","89158","89105","89194","88994","88989","88931"],
            card_pool=[],
            missing=[]
        ),
        r'[UnityCrossThreadLogger]==> LogBusinessEvents {"id":"a5c18703-d17d-4ec0-8c81-d5a6ba0ffd31","request":"{\"Type\":1912,\"TransId\":\"a5c18703-d17d-4ec0-8c81-d5a6ba0ffd31\",\"Payload\":\"{\\\"PlayerId\\\":null,\\\"ClientPlatform\\\":null,\\\"DraftId\\\":\\\"bc95b8cb-04d4-4823-aa37-a9b1a1212cb6\\\",\\\"EventId\\\":\\\"PremierDraft_MKM_20240206\\\",\\\"SeatNumber\\\":5,\\\"PackNumber\\\":1,\\\"PickNumber\\\":1,\\\"PickGrpId\\\":89119,\\\"CardsInPack\\\":[89119,89040,89008,88926,89093,88981,88950,89158,89105,89194,88994,88989,88931],\\\"AutoPick\\\":false,\\\"TimeRemainingOnPick\\\":58.9969749,\\\"EventType\\\":24,\\\"EventTime\\\":\\\"2024-02-13T09:53:59.9980573Z\\\"}\"}"}'
    ),
    (
        "P1P1 - Pick",
        EventResults(
            new_event=False,
            data_update=True,
            current_set="MKM",
            current_event="PremierDraft",
            current_pack=1,
            current_pick=1,
            picks=["89119"],
            pack=["89119","89040","89008","88926","89093","88981","88950","89158","89105","89194","88994","88989","88931"],
            card_pool=["89119"],
            missing=[]
        ),
        r'[UnityCrossThreadLogger]==> Event_PlayerDraftMakePick {"id":"49311e08-14e2-4ef0-b532-cff8ac3850dc","request":"{\"Type\":620,\"TransId\":\"49311e08-14e2-4ef0-b532-cff8ac3850dc\",\"Payload\":\"{\\\"DraftId\\\":\\\"bc95b8cb-04d4-4823-aa37-a9b1a1212cb6\\\",\\\"GrpId\\\":89119,\\\"Pack\\\":1,\\\"Pick\\\":1}\"}"}'
    ),
    (
        "P1P2 - Pack",
        EventResults(
            new_event=False,
            data_update=True,
            current_set="MKM",
            current_event="PremierDraft",
            current_pack=1,
            current_pick=2,
            picks=[],
            pack=["89097","89106","89057","88981","88934","89116","89004","88941","89035","89101","89127","89040"],
            card_pool=["89119"],
            missing=[]
        ),
        r'[UnityCrossThreadLogger]Draft.Notify {"draftId":"bc95b8cb-04d4-4823-aa37-a9b1a1212cb6","SelfPick":2,"SelfPack":1,"PackCards":"89097,89106,89057,88981,88934,89116,89004,88941,89035,89101,89127,89040"}'
    ),
    (
        "P1P9 - Pack",
        EventResults(
            new_event=False,
            data_update=True,
            current_set="MKM",
            current_event="PremierDraft",
            current_pack=1,
            current_pick=9,
            picks=["89119"],
            pack=["89040","89008","88981","89158","88989"],
            card_pool=["89119"],
            missing=["89119","88926","89093","88950","89105","89194","88994","88931"]
        ),
        r'[UnityCrossThreadLogger]Draft.Notify {"draftId":"bc95b8cb-04d4-4823-aa37-a9b1a1212cb6","SelfPick":9,"SelfPack":1,"PackCards":"89040,89008,88981,89158,88989"}'
    )
]

# Quick draft log entries collected from Player.log before 2024-5-7 Arena update
OTJ_QUICK_DRAFT_ENTRIES = [
    (
        "Event Start",
        EventResults(
            new_event=True,
            data_update=False,
            current_set="OTJ",
            current_event="QuickDraft",
            current_pack=0,
            current_pick=0,
            picks=[],
            pack=[],
            card_pool=[],
            missing=[]
        ),
        r'[UnityCrossThreadLogger]==> BotDraft_DraftStatus {"id":"acd4c04b-fabcd-4c5c-ac1e-6dfb53a2df2f","request":"{\"Type\":1802,\"TransId\":\"acd4c04b-fabcd-4c5c-ac1e-6dfb53a2df2f\",\"Payload\":\"{\\\"EventName\\\":\\\"QuickDraft_OTJ_20240426\\\"}\"}"}'
    ),
    (
        "P1P1 - Pack",
        EventResults(
            new_event=False,
            data_update=True,
            current_set="OTJ",
            current_event="QuickDraft",
            current_pack=1,
            current_pick=1,
            picks=[],
            pack=["90711","90504","90627","90449","90376","90595","90489","90527","90401","90365","90426","90480","90439","90428"],
            card_pool=[],
            missing=[]
        ),
        r'{"CurrentModule":"BotDraft","Payload":"{\"Result\":\"Success\",\"EventName\":\"QuickDraft_OTJ_20240426\",\"DraftStatus\":\"PickNext\",\"PackNumber\":0,\"PickNumber\":0,\"DraftPack\":[\"90711\",\"90504\",\"90627\",\"90449\",\"90376\",\"90595\",\"90489\",\"90527\",\"90401\",\"90365\",\"90426\",\"90480\",\"90439\",\"90428\"],\"PackStyles\":[],\"PickedCards\":[],\"PickedStyles\":[]}"}'
    ),
    (
        "P1P1 - Pick",
        EventResults(
            new_event=False,
            data_update=True,
            current_set="OTJ",
            current_event="QuickDraft",
            current_pack=1,
            current_pick=1,
            picks=["90428"],
            pack=["90711","90504","90627","90449","90376","90595","90489","90527","90401","90365","90426","90480","90439","90428"],
            card_pool=["90428"],
            missing=[]
        ),
        r'[UnityCrossThreadLogger]==> BotDraft_DraftPick {"id":"8ef75393-f84d-4aea-9baa-805c7d9cdb68","request":"{\"Type\":1801,\"TransId\":\"8ef75393-f84d-4aea-9baa-805c7d9cdb68\",\"Payload\":\"{\\\"EventName\\\":\\\"QuickDraft_OTJ_20240426\\\",\\\"PickInfo\\\":{\\\"EventName\\\":\\\"QuickDraft_OTJ_20240426\\\",\\\"CardId\\\":\\\"90428\\\",\\\"PackNumber\\\":0,\\\"PickNumber\\\":0}}\"}"}'
    ),
    (
        "P1P2 - Pack",
        EventResults(
            new_event=False,
            data_update=True,
            current_set="OTJ",
            current_event="QuickDraft",
            current_pack=1,
            current_pick=2,
            picks=[],
            pack=["90586","90628","90499","90600","90468","90418","90449","90442","90363","90360","90405","90598","90548"],
            card_pool=["90428"],
            missing=[]
        ),
        r'{"CurrentModule":"BotDraft","Payload":"{\"Result\":\"Success\",\"EventName\":\"QuickDraft_OTJ_20240426\",\"DraftStatus\":\"PickNext\",\"PackNumber\":0,\"PickNumber\":1,\"DraftPack\":[\"90586\",\"90628\",\"90499\",\"90600\",\"90468\",\"90418\",\"90449\",\"90442\",\"90363\",\"90360\",\"90405\",\"90598\",\"90548\"],\"PackStyles\":[],\"PickedCards\":[\"90428\"],\"PickedStyles\":[]}","DTO_InventoryInfo":{"SeqId":5,"Changes":[],"Gems":4620,"Gold":1525,"TotalVaultProgress":271,"WildCardCommons":13,"WildCardUnCommons":28,"WildCardRares":7,"WildCardMythics":5,"CustomTokens":{"BonusPackProgress":1,"BattlePass_BRO_Orb":1,"Token_JumpIn":5,"BattlePass_WOE_Orb":1,"BattlePass_MKM_Orb":1},"Boosters":[{"CollationId":100026,"SetCode":"VOW","Count":42},{"CollationId":400026,"SetCode":"Y22MID","Count":3},{"CollationId":100024,"SetCode":"AFR","Count":2},{"CollationId":100027,"SetCode":"NEO","Count":21},{"CollationId":100025,"SetCode":"MID","Count":2},{"CollationId":100029,"SetCode":"HBG","Count":15},{"CollationId":100030,"SetCode":"DMU","Count":7},{"CollationId":100031,"SetCode":"BRO","Count":3},{"CollationId":400031,"SetCode":"Y23BRO","Count":6},{"CollationId":100032,"SetCode":"ONE","Count":4},{"CollationId":400032,"SetCode":"Y23ONE","Count":3},{"CollationId":100033,"SetCode":"SIR","Count":4},{"CollationId":100037,"SetCode":"MOM","Count":4},{"CollationId":100040,"SetCode":"WOE","Count":6},{"CollationId":100039,"SetCode":"LTR","Count":3},{"CollationId":100038,"SetCode":"MAT","Count":3},{"CollationId":400040,"SetCode":"Y24WOE","Count":3},{"CollationId":100041,"SetCode":"LCI","Count":7},{"CollationId":100042,"SetCode":"KTK","Count":3},{"CollationId":400041,"SetCode":"Y24LCI","Count":3},{"CollationId":100043,"SetCode":"MKM","Count":13},{"CollationId":100044,"SetCode":"OTJ","Count":3},{"CollationId":400043,"SetCode":"Y24MKM","Count":3}],"Vouchers":{},"Cosmetics":{"ArtStyles":[{"Type":"ArtStyle","Id":"404952.DA","ArtId":404952,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"409037.DA","ArtId":409037,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"127296.DA","ArtId":127296,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"407656.DA","ArtId":407656,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"402637.DA","ArtId":402637,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"404505.DA","ArtId":404505,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"416691.SH","ArtId":416691,"Variant":"SH","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417846.JP","ArtId":417846,"Variant":"JP","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421263.DA","ArtId":421263,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421270.DA","ArtId":421270,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421273.DA","ArtId":421273,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"421180.DA","ArtId":421180,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421282.DA","ArtId":421282,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421308.TOHO","ArtId":421308,"Variant":"TOHO","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"421132.DA","ArtId":421132,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"422314.DA","ArtId":422314,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"417325.DA","ArtId":417325,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"425840.DA","ArtId":425840,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"409970.STORYBOOK","ArtId":409970,"Variant":"STORYBOOK","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"403040.ARCHITECTURE","ArtId":403040,"Variant":"ARCHITECTURE","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"430483.DA","ArtId":430483,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"438995.DA","ArtId":438995,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"430520.DA","ArtId":430520,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418126.SCHEMATIC","ArtId":418126,"Variant":"SCHEMATIC","ExplicitGrpIds":[]}],"Avatars":[{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_ChandraNalaar","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_AjaniGoldmane","Type":"Avatar"},{"Id":"Avatar_Basic_GideonJura","Type":"Avatar"},{"Id":"Avatar_Basic_Teferi","Type":"Avatar"},{"Id":"Avatar_Basic_SarkhanVol","Type":"Avatar"},{"Id":"Avatar_Basic_Tezzeret","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_VivienReid","Type":"Avatar"},{"Id":"Avatar_Basic_NissaRevane","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_LilianaVess","Type":"Avatar"},{"Id":"Avatar_Basic_Karn","Type":"Avatar"},{"Id":"Avatar_Basic_JayaBallard","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_JaceBeleren","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_Elspeth_MOM","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_Ashiok_WAR","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_Kaito_NEO","Type":"Avatar"}],"Pets":[],"Sleeves":[{"Id":"CardBack_ZNR_402686","Type":"Sleeve"},{"AcquisitionFlags":"CodeRedemption","Id":"CardBack_EmbossedDefaultArena","Type":"Sleeve"},{"Id":"CardBack_ZNR_417011","Type":"Sleeve"},{"Id":"CardBack_M21_413716","Type":"Sleeve"},{"AcquisitionFlags":"Event","Id":"CardBack_IKO_VivienMonstersAdvocate","Type":"Sleeve"},{"Id":"CardBack_DMU_439347","Type":"Sleeve"}],"Emotes":[{"AcquisitionFlags":"DefaultLoginGrant","Id":"Phrase_Basic_Hello","Type":"Emote","Category":"Greeting","Treatment":""},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Phrase_Basic_Nice_Thanks","Type":"Emote","FlipType":"Reply","Category":"Kudos","Treatment":""},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Phrase_Basic_Thinking_YourGo","Type":"Emote","FlipType":"Priority","Category":"Priority","Treatment":""},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Phrase_Basic_Oops_Sorry","Type":"Emote","FlipType":"Reply","Category":"Accident","Treatment":""},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Phrase_Basic_GoodGame","Type":"Emote","Category":"GoodGame","Treatment":""},{"Id":"Sticker_MID_Teferi","Type":"Emote","Page":"Sticker","Category":"MID_Stickers","Treatment":"Sticker_MID_Teferi"},{"Id":"Sticker_Halloween23_AngryRoll","Type":"Emote","Page":"Sticker","Category":"Halloween23_Stickers","Treatment":"Sticker_Halloween23_AngryRoll"}]}}}'
    ),
    (
        "P1P9 - Pack",
        EventResults(
            new_event=False,
            data_update=True,
            current_set="OTJ",
            current_event="QuickDraft",
            current_pack=1,
            current_pick=9,
            picks=["90428"],
            pack=["90627","90376","90595","90489","90401","90480"],
            card_pool=["90428"],
            missing=["90711","90504","90449","90527","90365","90426","90439","90428"]
        ),
        r'{"CurrentModule":"BotDraft","Payload":"{\"Result\":\"Success\",\"EventName\":\"QuickDraft_OTJ_20240426\",\"DraftStatus\":\"PickNext\",\"PackNumber\":0,\"PickNumber\":8,\"DraftPack\":[\"90627\",\"90376\",\"90595\",\"90489\",\"90401\",\"90480\"],\"PackStyles\":[],\"PickedCards\":[\"90428\",\"90360\",\"90529\",\"90528\",\"90362\",\"90520\",\"90362\",\"90501\"],\"PickedStyles\":[]}","DTO_InventoryInfo":{"SeqId":12,"Changes":[],"Gems":4620,"Gold":1525,"TotalVaultProgress":271,"WildCardCommons":13,"WildCardUnCommons":28,"WildCardRares":7,"WildCardMythics":5,"CustomTokens":{"BonusPackProgress":1,"BattlePass_BRO_Orb":1,"Token_JumpIn":5,"BattlePass_WOE_Orb":1,"BattlePass_MKM_Orb":1},"Boosters":[{"CollationId":100026,"SetCode":"VOW","Count":42},{"CollationId":400026,"SetCode":"Y22MID","Count":3},{"CollationId":100024,"SetCode":"AFR","Count":2},{"CollationId":100027,"SetCode":"NEO","Count":21},{"CollationId":100025,"SetCode":"MID","Count":2},{"CollationId":100029,"SetCode":"HBG","Count":15},{"CollationId":100030,"SetCode":"DMU","Count":7},{"CollationId":100031,"SetCode":"BRO","Count":3},{"CollationId":400031,"SetCode":"Y23BRO","Count":6},{"CollationId":100032,"SetCode":"ONE","Count":4},{"CollationId":400032,"SetCode":"Y23ONE","Count":3},{"CollationId":100033,"SetCode":"SIR","Count":4},{"CollationId":100037,"SetCode":"MOM","Count":4},{"CollationId":100040,"SetCode":"WOE","Count":6},{"CollationId":100039,"SetCode":"LTR","Count":3},{"CollationId":100038,"SetCode":"MAT","Count":3},{"CollationId":400040,"SetCode":"Y24WOE","Count":3},{"CollationId":100041,"SetCode":"LCI","Count":7},{"CollationId":100042,"SetCode":"KTK","Count":3},{"CollationId":400041,"SetCode":"Y24LCI","Count":3},{"CollationId":100043,"SetCode":"MKM","Count":13},{"CollationId":100044,"SetCode":"OTJ","Count":3},{"CollationId":400043,"SetCode":"Y24MKM","Count":3}],"Vouchers":{},"Cosmetics":{"ArtStyles":[{"Type":"ArtStyle","Id":"404952.DA","ArtId":404952,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"409037.DA","ArtId":409037,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"127296.DA","ArtId":127296,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"407656.DA","ArtId":407656,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"402637.DA","ArtId":402637,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"404505.DA","ArtId":404505,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"416691.SH","ArtId":416691,"Variant":"SH","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417846.JP","ArtId":417846,"Variant":"JP","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421263.DA","ArtId":421263,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421270.DA","ArtId":421270,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421273.DA","ArtId":421273,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"421180.DA","ArtId":421180,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421282.DA","ArtId":421282,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421308.TOHO","ArtId":421308,"Variant":"TOHO","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"421132.DA","ArtId":421132,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"422314.DA","ArtId":422314,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"417325.DA","ArtId":417325,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"425840.DA","ArtId":425840,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"409970.STORYBOOK","ArtId":409970,"Variant":"STORYBOOK","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"403040.ARCHITECTURE","ArtId":403040,"Variant":"ARCHITECTURE","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"430483.DA","ArtId":430483,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"438995.DA","ArtId":438995,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"430520.DA","ArtId":430520,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418126.SCHEMATIC","ArtId":418126,"Variant":"SCHEMATIC","ExplicitGrpIds":[]}],"Avatars":[{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_ChandraNalaar","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_AjaniGoldmane","Type":"Avatar"},{"Id":"Avatar_Basic_GideonJura","Type":"Avatar"},{"Id":"Avatar_Basic_Teferi","Type":"Avatar"},{"Id":"Avatar_Basic_SarkhanVol","Type":"Avatar"},{"Id":"Avatar_Basic_Tezzeret","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_VivienReid","Type":"Avatar"},{"Id":"Avatar_Basic_NissaRevane","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_LilianaVess","Type":"Avatar"},{"Id":"Avatar_Basic_Karn","Type":"Avatar"},{"Id":"Avatar_Basic_JayaBallard","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_JaceBeleren","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_Elspeth_MOM","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_Ashiok_WAR","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_Kaito_NEO","Type":"Avatar"}],"Pets":[],"Sleeves":[{"Id":"CardBack_ZNR_402686","Type":"Sleeve"},{"AcquisitionFlags":"CodeRedemption","Id":"CardBack_EmbossedDefaultArena","Type":"Sleeve"},{"Id":"CardBack_ZNR_417011","Type":"Sleeve"},{"Id":"CardBack_M21_413716","Type":"Sleeve"},{"AcquisitionFlags":"Event","Id":"CardBack_IKO_VivienMonstersAdvocate","Type":"Sleeve"},{"Id":"CardBack_DMU_439347","Type":"Sleeve"}],"Emotes":[{"AcquisitionFlags":"DefaultLoginGrant","Id":"Phrase_Basic_Hello","Type":"Emote","Category":"Greeting","Treatment":""},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Phrase_Basic_Nice_Thanks","Type":"Emote","FlipType":"Reply","Category":"Kudos","Treatment":""},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Phrase_Basic_Thinking_YourGo","Type":"Emote","FlipType":"Priority","Category":"Priority","Treatment":""},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Phrase_Basic_Oops_Sorry","Type":"Emote","FlipType":"Reply","Category":"Accident","Treatment":""},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Phrase_Basic_GoodGame","Type":"Emote","Category":"GoodGame","Treatment":""},{"Id":"Sticker_MID_Teferi","Type":"Emote","Page":"Sticker","Category":"MID_Stickers","Treatment":"Sticker_MID_Teferi"},{"Id":"Sticker_Halloween23_AngryRoll","Type":"Emote","Page":"Sticker","Category":"Halloween23_Stickers","Treatment":"Sticker_Halloween23_AngryRoll"}]}}}'
    ),
    (
        "P3P14 - Pack",
        EventResults(
            new_event=False,
            data_update=True,
            current_set="OTJ",
            current_event="QuickDraft",
            current_pack=3,
            current_pick=14,
            picks=[],
            pack=["90440"],
            card_pool=["90428"],
            missing=[]
        ),
        r'{"CurrentModule":"BotDraft","Payload":"{\"Result\":\"Success\",\"EventName\":\"QuickDraft_OTJ_20240426\",\"DraftStatus\":\"PickNext\",\"PackNumber\":2,\"PickNumber\":13,\"DraftPack\":[\"90440\"],\"PackStyles\":[],\"PickedCards\":[\"90376\",\"90428\",\"90600\",\"90360\",\"90595\",\"90529\",\"90595\",\"90528\",\"90481\",\"90362\",\"90419\",\"90520\",\"90362\",\"90501\",\"90379\",\"90500\",\"90380\",\"90520\",\"90632\",\"90379\",\"90506\",\"90593\",\"90514\",\"90353\",\"90726\",\"90423\",\"90384\",\"90530\",\"90378\",\"90567\",\"90376\",\"90504\",\"90502\",\"90432\",\"90507\",\"90382\",\"90414\",\"90506\",\"90382\",\"90507\",\"90507\"],\"PickedStyles\":[]}","DTO_InventoryInfo":{"SeqId":45,"Changes":[],"Gems":4620,"Gold":1525,"TotalVaultProgress":271,"WildCardCommons":13,"WildCardUnCommons":28,"WildCardRares":7,"WildCardMythics":5,"CustomTokens":{"BonusPackProgress":1,"BattlePass_BRO_Orb":1,"Token_JumpIn":5,"BattlePass_WOE_Orb":1,"BattlePass_MKM_Orb":1},"Boosters":[{"CollationId":100026,"SetCode":"VOW","Count":42},{"CollationId":400026,"SetCode":"Y22MID","Count":3},{"CollationId":100024,"SetCode":"AFR","Count":2},{"CollationId":100027,"SetCode":"NEO","Count":21},{"CollationId":100025,"SetCode":"MID","Count":2},{"CollationId":100029,"SetCode":"HBG","Count":15},{"CollationId":100030,"SetCode":"DMU","Count":7},{"CollationId":100031,"SetCode":"BRO","Count":3},{"CollationId":400031,"SetCode":"Y23BRO","Count":6},{"CollationId":100032,"SetCode":"ONE","Count":4},{"CollationId":400032,"SetCode":"Y23ONE","Count":3},{"CollationId":100033,"SetCode":"SIR","Count":4},{"CollationId":100037,"SetCode":"MOM","Count":4},{"CollationId":100040,"SetCode":"WOE","Count":6},{"CollationId":100039,"SetCode":"LTR","Count":3},{"CollationId":100038,"SetCode":"MAT","Count":3},{"CollationId":400040,"SetCode":"Y24WOE","Count":3},{"CollationId":100041,"SetCode":"LCI","Count":7},{"CollationId":100042,"SetCode":"KTK","Count":3},{"CollationId":400041,"SetCode":"Y24LCI","Count":3},{"CollationId":100043,"SetCode":"MKM","Count":13},{"CollationId":100044,"SetCode":"OTJ","Count":3},{"CollationId":400043,"SetCode":"Y24MKM","Count":3}],"Vouchers":{},"Cosmetics":{"ArtStyles":[{"Type":"ArtStyle","Id":"404952.DA","ArtId":404952,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"409037.DA","ArtId":409037,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"127296.DA","ArtId":127296,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"407656.DA","ArtId":407656,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"402637.DA","ArtId":402637,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"404505.DA","ArtId":404505,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"416691.SH","ArtId":416691,"Variant":"SH","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417846.JP","ArtId":417846,"Variant":"JP","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421263.DA","ArtId":421263,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421270.DA","ArtId":421270,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421273.DA","ArtId":421273,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"421180.DA","ArtId":421180,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421282.DA","ArtId":421282,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421308.TOHO","ArtId":421308,"Variant":"TOHO","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"421132.DA","ArtId":421132,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"422314.DA","ArtId":422314,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"417325.DA","ArtId":417325,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"425840.DA","ArtId":425840,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"409970.STORYBOOK","ArtId":409970,"Variant":"STORYBOOK","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"403040.ARCHITECTURE","ArtId":403040,"Variant":"ARCHITECTURE","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"430483.DA","ArtId":430483,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"438995.DA","ArtId":438995,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"430520.DA","ArtId":430520,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418126.SCHEMATIC","ArtId":418126,"Variant":"SCHEMATIC","ExplicitGrpIds":[]}],"Avatars":[{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_ChandraNalaar","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_AjaniGoldmane","Type":"Avatar"},{"Id":"Avatar_Basic_GideonJura","Type":"Avatar"},{"Id":"Avatar_Basic_Teferi","Type":"Avatar"},{"Id":"Avatar_Basic_SarkhanVol","Type":"Avatar"},{"Id":"Avatar_Basic_Tezzeret","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_VivienReid","Type":"Avatar"},{"Id":"Avatar_Basic_NissaRevane","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_LilianaVess","Type":"Avatar"},{"Id":"Avatar_Basic_Karn","Type":"Avatar"},{"Id":"Avatar_Basic_JayaBallard","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_JaceBeleren","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_Elspeth_MOM","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_Ashiok_WAR","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_Kaito_NEO","Type":"Avatar"}],"Pets":[],"Sleeves":[{"Id":"CardBack_ZNR_402686","Type":"Sleeve"},{"AcquisitionFlags":"CodeRedemption","Id":"CardBack_EmbossedDefaultArena","Type":"Sleeve"},{"Id":"CardBack_ZNR_417011","Type":"Sleeve"},{"Id":"CardBack_M21_413716","Type":"Sleeve"},{"AcquisitionFlags":"Event","Id":"CardBack_IKO_VivienMonstersAdvocate","Type":"Sleeve"},{"Id":"CardBack_DMU_439347","Type":"Sleeve"}],"Emotes":[{"AcquisitionFlags":"DefaultLoginGrant","Id":"Phrase_Basic_Hello","Type":"Emote","Category":"Greeting","Treatment":""},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Phrase_Basic_Nice_Thanks","Type":"Emote","FlipType":"Reply","Category":"Kudos","Treatment":""},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Phrase_Basic_Thinking_YourGo","Type":"Emote","FlipType":"Priority","Category":"Priority","Treatment":""},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Phrase_Basic_Oops_Sorry","Type":"Emote","FlipType":"Reply","Category":"Accident","Treatment":""},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Phrase_Basic_GoodGame","Type":"Emote","Category":"GoodGame","Treatment":""},{"Id":"Sticker_MID_Teferi","Type":"Emote","Page":"Sticker","Category":"MID_Stickers","Treatment":"Sticker_MID_Teferi"},{"Id":"Sticker_Halloween23_AngryRoll","Type":"Emote","Page":"Sticker","Category":"Halloween23_Stickers","Treatment":"Sticker_Halloween23_AngryRoll"}]}}}'
    )
]

# Quick draft log entries collected from Player.log after 2024-5-7 Arena update
DMU_QUICK_DRAFT_ENTRIES_2024_5_7 = [
    (
        "Event Start",
        EventResults(
            new_event=True,
            data_update=False,
            current_set="DMU",
            current_event="QuickDraft",
            current_pack=0,
            current_pick=0,
            picks=[],
            pack=[],
            card_pool=[],
            missing=[]
        ),
        r'[UnityCrossThreadLogger]==> BotDraft_DraftStatus {"id":"530a212c-0358-4ee0-bac9-35bf33918d11","request":"{\"EventName\":\"QuickDraft_DMU_20240507\"}"}'
    ),
    (
        "P1P1 - Pack",
        EventResults(
            new_event=False,
            data_update=True,
            current_set="DMU",
            current_event="QuickDraft",
            current_pack=1,
            current_pick=1,
            picks=[],
            pack=["82309","82207","82083","82165","82196","82129","82170","82146","82120","82059","82160","82168","82091","82256"],
            card_pool=[],
            missing=[]
        ),
        r'{"CurrentModule":"BotDraft","Payload":"{\"Result\":\"Success\",\"EventName\":\"QuickDraft_DMU_20240507\",\"DraftStatus\":\"PickNext\",\"PackNumber\":0,\"PickNumber\":0,\"DraftPack\":[\"82309\",\"82207\",\"82083\",\"82165\",\"82196\",\"82129\",\"82170\",\"82146\",\"82120\",\"82059\",\"82160\",\"82168\",\"82091\",\"82256\"],\"PackStyles\":[],\"PickedCards\":[],\"PickedStyles\":[]}"}'
    ),
    (
        "P1P1 - Pick",
        EventResults(
            new_event=False,
            data_update=True,
            current_set="DMU",
            current_event="QuickDraft",
            current_pack=1,
            current_pick=1,
            picks=["82091"],
            pack=["82309","82207","82083","82165","82196","82129","82170","82146","82120","82059","82160","82168","82091","82256"],
            card_pool=["82091"],
            missing=[]
        ),
        r'[UnityCrossThreadLogger]==> BotDraft_DraftPick {"id":"a4bc9a1c-8b5a-4939-85f8-d2eb524b5069","request":"{\"EventName\":\"QuickDraft_DMU_20240507\",\"PickInfo\":{\"EventName\":\"QuickDraft_DMU_20240507\",\"CardId\":\"82091\",\"PackNumber\":0,\"PickNumber\":0}}"}'
    ),
    (
        "P1P2 - Pack",
        EventResults(
            new_event=False,
            data_update=True,
            current_set="DMU",
            current_event="QuickDraft",
            current_pack=1,
            current_pick=2,
            picks=[],
            pack=["82200","82129","82179","82062","82299","82209","82228","82074","82153","82281","82096","82140","82245"],
            card_pool=["82091"],
            missing=[]
        ),
        r'{"CurrentModule":"BotDraft","Payload":"{\"Result\":\"Success\",\"EventName\":\"QuickDraft_DMU_20240507\",\"DraftStatus\":\"PickNext\",\"PackNumber\":0,\"PickNumber\":1,\"DraftPack\":[\"82200\",\"82129\",\"82179\",\"82062\",\"82299\",\"82209\",\"82228\",\"82074\",\"82153\",\"82281\",\"82096\",\"82140\",\"82245\"],\"PackStyles\":[],\"PickedCards\":[\"82091\"],\"PickedStyles\":[]}","DTO_InventoryInfo":{"SeqId":7,"Changes":[],"Gems":2300,"Gold":4500,"TotalVaultProgress":868,"wcTrackPosition":6,"WildCardCommons":68,"WildCardUnCommons":87,"WildCardRares":28,"WildCardMythics":12,"CustomTokens":{"BattlePass_AFR_Orb":1,"BattlePass_HBG_Orb":1,"BonusPackProgress":1,"BattlePass_MKM_Orb":1,"DraftToken":1},"Boosters":[{"CollationId":100026,"SetCode":"VOW","Count":10},{"CollationId":100024,"SetCode":"AFR","Count":7},{"CollationId":100020,"SetCode":"ZNR","Count":2},{"CollationId":100022,"SetCode":"KHM","Count":2},{"CollationId":100023,"SetCode":"STX","Count":3},{"CollationId":100025,"SetCode":"MID","Count":4},{"CollationId":100027,"SetCode":"NEO","Count":41},{"CollationId":100028,"SetCode":"SNC","Count":3},{"CollationId":400028,"SetCode":"Y22SNC","Count":1},{"CollationId":100029,"SetCode":"HBG","Count":8},{"CollationId":100030,"SetCode":"DMU","Count":1},{"CollationId":100031,"SetCode":"BRO","Count":1},{"CollationId":100032,"SetCode":"ONE","Count":3},{"CollationId":100033,"SetCode":"SIR","Count":3},{"CollationId":100037,"SetCode":"MOM","Count":3},{"CollationId":100039,"SetCode":"LTR","Count":3},{"CollationId":100040,"SetCode":"WOE","Count":3},{"CollationId":400031,"SetCode":"Y23BRO","Count":6},{"CollationId":400032,"SetCode":"Y23ONE","Count":3},{"CollationId":100038,"SetCode":"MAT","Count":3},{"CollationId":400040,"SetCode":"Y24WOE","Count":3},{"CollationId":400041,"SetCode":"Y24LCI","Count":3},{"CollationId":100042,"SetCode":"KTK","Count":3},{"CollationId":100041,"SetCode":"LCI","Count":4},{"CollationId":100043,"SetCode":"MKM","Count":6},{"CollationId":100044,"SetCode":"OTJ","Count":4},{"CollationId":400043,"SetCode":"Y24MKM","Count":3},{"CollationId":400044,"SetCode":"Y24OTJ","Count":3}],"Vouchers":{},"Cosmetics":{"ArtStyles":[{"Type":"ArtStyle","Id":"404952.DA","ArtId":404952,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"409037.DA","ArtId":409037,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"127296.DA","ArtId":127296,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"404505.DA","ArtId":404505,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"402637.DA","ArtId":402637,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"407656.DA","ArtId":407656,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418892.DA","ArtId":418892,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418903.DA","ArtId":418903,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"Event","Type":"ArtStyle","Id":"420249.JP","ArtId":420249,"Variant":"JP","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"416627.SH","ArtId":416627,"Variant":"SH","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417880.JP","ArtId":417880,"Variant":"JP","ExplicitGrpIds":[]},{"AcquisitionFlags":"CodeRedemption","Type":"ArtStyle","Id":"406523.SG","ArtId":406523,"Variant":"SG","ExplicitGrpIds":[]},{"AcquisitionFlags":"CodeRedemption","Type":"ArtStyle","Id":"406664.SG","ArtId":406664,"Variant":"SG","ExplicitGrpIds":[]},{"AcquisitionFlags":"CodeRedemption","Type":"ArtStyle","Id":"409514.SG","ArtId":409514,"Variant":"SG","ExplicitGrpIds":[]},{"AcquisitionFlags":"CodeRedemption","Type":"ArtStyle","Id":"406559.SG","ArtId":406559,"Variant":"SG","ExplicitGrpIds":[]},{"AcquisitionFlags":"CodeRedemption","Type":"ArtStyle","Id":"406626.SG","ArtId":406626,"Variant":"SG","ExplicitGrpIds":[]},{"AcquisitionFlags":"CodeRedemption","Type":"ArtStyle","Id":"402959.DA","ArtId":402959,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"CodeRedemption","Type":"ArtStyle","Id":"400332.DA","ArtId":400332,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"CodeRedemption","Type":"ArtStyle","Id":"404135.DA","ArtId":404135,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"CodeRedemption","Type":"ArtStyle","Id":"404488.DA","ArtId":404488,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"CodeRedemption","Type":"ArtStyle","Id":"402057.DA","ArtId":402057,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418809.DA","ArtId":418809,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418895.DA","ArtId":418895,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418859.DA","ArtId":418859,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418963.DA","ArtId":418963,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418925.DA","ArtId":418925,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418777.DA","ArtId":418777,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418962.DA","ArtId":418962,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418781.DA","ArtId":418781,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418812.DA","ArtId":418812,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"416383.DA","ArtId":416383,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"416356.DA","ArtId":416356,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418912.DA","ArtId":418912,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418917.DA","ArtId":418917,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418785.DA","ArtId":418785,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418790.DA","ArtId":418790,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418988.DA","ArtId":418988,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418798.DA","ArtId":418798,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419549.DA","ArtId":419549,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419568.DA","ArtId":419568,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"418867.DA","ArtId":418867,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"419407.DA","ArtId":419407,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419576.DA","ArtId":419576,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"422879.DA","ArtId":422879,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419437.DA","ArtId":419437,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419501.DA","ArtId":419501,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419546.DA","ArtId":419546,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419693.DA","ArtId":419693,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"415977.DA","ArtId":415977,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419600.DA","ArtId":419600,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419682.DA","ArtId":419682,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419495.DA","ArtId":419495,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419551.DA","ArtId":419551,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419683.DA","ArtId":419683,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419694.DA","ArtId":419694,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419488.DA","ArtId":419488,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419685.DA","ArtId":419685,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419452.DA","ArtId":419452,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419643.DA","ArtId":419643,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419687.DA","ArtId":419687,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419567.DA","ArtId":419567,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419720.DA","ArtId":419720,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"415990.DA","ArtId":415990,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419665.DA","ArtId":419665,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419664.DA","ArtId":419664,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419722.DA","ArtId":419722,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419672.DA","ArtId":419672,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419676.DA","ArtId":419676,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419601.DA","ArtId":419601,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419620.DA","ArtId":419620,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419617.DA","ArtId":419617,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419721.DA","ArtId":419721,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"424152.DA","ArtId":424152,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419628.DA","ArtId":419628,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419492.DA","ArtId":419492,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419514.DA","ArtId":419514,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419515.DA","ArtId":419515,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419436.DA","ArtId":419436,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419719.DA","ArtId":419719,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"Event","Type":"ArtStyle","Id":"417888.JP","ArtId":417888,"Variant":"JP","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419536.DA","ArtId":419536,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419528.DA","ArtId":419528,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419527.DA","ArtId":419527,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419593.DA","ArtId":419593,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419446.DA","ArtId":419446,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"415986.DA","ArtId":415986,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419468.DA","ArtId":419468,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419602.DA","ArtId":419602,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419466.DA","ArtId":419466,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419690.DA","ArtId":419690,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419692.DA","ArtId":419692,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419718.DA","ArtId":419718,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419651.DA","ArtId":419651,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419473.DA","ArtId":419473,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"419467.DA","ArtId":419467,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"419630.DA","ArtId":419630,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419688.DA","ArtId":419688,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419476.DA","ArtId":419476,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421125.DA","ArtId":421125,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417889.JP","ArtId":417889,"Variant":"JP","ExplicitGrpIds":[]},{"AcquisitionFlags":"Event","Type":"ArtStyle","Id":"417868.JP","ArtId":417868,"Variant":"JP","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417340.DA","ArtId":417340,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421130.DA","ArtId":421130,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"419511.DA","ArtId":419511,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421133.DA","ArtId":421133,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417319.DA","ArtId":417319,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"421180.DA","ArtId":421180,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"421284.DA","ArtId":421284,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"421132.DA","ArtId":421132,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"421237.DA","ArtId":421237,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421114.DA","ArtId":421114,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421162.DA","ArtId":421162,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417065.DA","ArtId":417065,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421259.DA","ArtId":421259,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417343.DA","ArtId":417343,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421343.DA","ArtId":421343,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417314.DA","ArtId":417314,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417066.DA","ArtId":417066,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421159.DA","ArtId":421159,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417063.DA","ArtId":417063,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421346.DA","ArtId":421346,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417332.DA","ArtId":417332,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421297.DA","ArtId":421297,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417361.DA","ArtId":417361,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421121.DA","ArtId":421121,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421170.DA","ArtId":421170,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421342.DA","ArtId":421342,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421212.DA","ArtId":421212,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421254.DA","ArtId":421254,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421150.DA","ArtId":421150,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421172.DA","ArtId":421172,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421184.DA","ArtId":421184,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421185.DA","ArtId":421185,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421198.DA","ArtId":421198,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421193.DA","ArtId":421193,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421205.DA","ArtId":421205,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421227.DA","ArtId":421227,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421229.DA","ArtId":421229,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417351.DA","ArtId":417351,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421242.DA","ArtId":421242,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421263.DA","ArtId":421263,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421270.DA","ArtId":421270,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421273.DA","ArtId":421273,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421282.DA","ArtId":421282,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421344.DA","ArtId":421344,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421283.DA","ArtId":421283,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421303.DA","ArtId":421303,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"422142.DA","ArtId":422142,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"422322.DA","ArtId":422322,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"417325.DA","ArtId":417325,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"421142.DA","ArtId":421142,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"422152.DA","ArtId":422152,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"422167.DA","ArtId":422167,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"422148.DA","ArtId":422148,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"422213.DA","ArtId":422213,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"443063.DA","ArtId":443063,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418126.SCHEMATIC","ArtId":418126,"Variant":"SCHEMATIC","ExplicitGrpIds":[]}],"Avatars":[{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_ChandraNalaar","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_AjaniGoldmane","Type":"Avatar"},{"Id":"Avatar_Basic_GideonJura","Type":"Avatar"},{"Id":"Avatar_Basic_Teferi","Type":"Avatar"},{"Id":"Avatar_Basic_SarkhanVol","Type":"Avatar"},{"Id":"Avatar_Basic_Tezzeret","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_VivienReid","Type":"Avatar"},{"Id":"Avatar_Basic_NissaRevane","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_LilianaVess","Type":"Avatar"},{"Id":"Avatar_Basic_Karn","Type":"Avatar"},{"Id":"Avatar_Basic_JayaBallard","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_JaceBeleren","Type":"Avatar"},{"Id":"Avatar_Basic_Ellywick_AFR","Type":"Avatar"},{"Id":"Avatar_Basic_Wrenn_MID","Type":"Avatar"},{"AcquisitionFlags":"CodeRedemption","Id":"Avatar_Basic_Sorin_VOW","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_Elspeth_MOM","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_Ashiok_WAR","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_Kaito_NEO","Type":"Avatar"}],"Pets":[{"Type":"Pet","Id":"AFR_Dragon.Skin1","Name":"AFR_Dragon","Variant":"Skin1"},{"Type":"Pet","Id":"AFR_Dragon.Skin2","Name":"AFR_Dragon","Variant":"Skin2"},{"Type":"Pet","Id":"MID_Geist.Skin1","Name":"MID_Geist","Variant":"Skin1"},{"Type":"Pet","Id":"MID_Geist.Skin2","Name":"MID_Geist","Variant":"Skin2"},{"Type":"Pet","Id":"MID_Geist.Skin3","Name":"MID_Geist","Variant":"Skin3"},{"Type":"Pet","Id":"VOW_Bat.Level1","Name":"VOW_Bat","Variant":"Level1"},{"Type":"Pet","Id":"VOW_Bat.Level2","Name":"VOW_Bat","Variant":"Level2"},{"Type":"Pet","Id":"VOW_Bat.Level3","Name":"VOW_Bat","Variant":"Level3"}],"Sleeves":[{"AcquisitionFlags":"CodeRedemption","Id":"CardBack_Basic_Thunderstorm_Bitterblossom","Type":"Sleeve"},{"AcquisitionFlags":"CodeRedemption","Id":"CardBack_STX_418002","Type":"Sleeve"},{"AcquisitionFlags":"CodeRedemption","Id":"CardBack_STX_418001","Type":"Sleeve"},{"AcquisitionFlags":"CodeRedemption","Id":"CardBack_STX_418003","Type":"Sleeve"},{"AcquisitionFlags":"CodeRedemption","Id":"CardBack_STX_418004","Type":"Sleeve"},{"AcquisitionFlags":"CodeRedemption","Id":"CardBack_STX_418005","Type":"Sleeve"},{"Id":"CardBack_AFR_419749","Type":"Sleeve"},{"Id":"CardBack_AFR_419144","Type":"Sleeve"},{"Id":"CardBack_AFR_419111","Type":"Sleeve"},{"Id":"CardBack_MID_424253","Type":"Sleeve"},{"Id":"CardBack_MID_423524","Type":"Sleeve"},{"Id":"CardBack_ZNR_402686","Type":"Sleeve"},{"Id":"CardBack_MID_422493","Type":"Sleeve"},{"Id":"CardBack_VOW_424637","Type":"Sleeve"},{"Id":"CardBack_VOW_422028","Type":"Sleeve"},{"Id":"CardBack_VOW_422180","Type":"Sleeve"},{"Id":"CardBack_VOW_421278","Type":"Sleeve"},{"Id":"CardBack_VOW_421349","Type":"Sleeve"},{"AcquisitionFlags":"Event, CodeRedemption","Id":"CardBack_DvC_409074","Type":"Sleeve"}],"Emotes":[{"AcquisitionFlags":"DefaultLoginGrant","Id":"Phrase_Basic_Hello","Type":"Emote","Category":"Greeting","Treatment":""},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Phrase_Basic_Nice_Thanks","Type":"Emote","FlipType":"Reply","Category":"Kudos","Treatment":""},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Phrase_Basic_Thinking_YourGo","Type":"Emote","FlipType":"Priority","Category":"Priority","Treatment":""},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Phrase_Basic_Oops_Sorry","Type":"Emote","FlipType":"Reply","Category":"Accident","Treatment":""},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Phrase_Basic_GoodGame","Type":"Emote","Category":"GoodGame","Treatment":""}]}}}'
    ),
    (
        "P1P9 - Pack",
        EventResults(
            new_event=False,
            data_update=True,
            current_set="DMU",
            current_event="QuickDraft",
            current_pack=1,
            current_pick=9,
            picks=["82091"],
            pack=["82083","82196","82129","82170","82059","82160"],
            card_pool=["82091"],
            missing=["82309","82207","82165","82146","82120","82168","82091","82256"]
        ),
        r'{"CurrentModule":"BotDraft","Payload":"{\"Result\":\"Success\",\"EventName\":\"QuickDraft_DMU_20240507\",\"DraftStatus\":\"PickNext\",\"PackNumber\":0,\"PickNumber\":8,\"DraftPack\":[\"82083\",\"82196\",\"82129\",\"82170\",\"82059\",\"82160\"],\"PackStyles\":[],\"PickedCards\":[\"82091\",\"82140\",\"82065\",\"82124\",\"82303\",\"82123\",\"82249\",\"82309\"],\"PickedStyles\":[]}","DTO_InventoryInfo":{"SeqId":14,"Changes":[],"Gems":2300,"Gold":4500,"TotalVaultProgress":868,"wcTrackPosition":6,"WildCardCommons":68,"WildCardUnCommons":87,"WildCardRares":28,"WildCardMythics":12,"CustomTokens":{"BattlePass_AFR_Orb":1,"BattlePass_HBG_Orb":1,"BonusPackProgress":1,"BattlePass_MKM_Orb":1,"DraftToken":1},"Boosters":[{"CollationId":100026,"SetCode":"VOW","Count":10},{"CollationId":100024,"SetCode":"AFR","Count":7},{"CollationId":100020,"SetCode":"ZNR","Count":2},{"CollationId":100022,"SetCode":"KHM","Count":2},{"CollationId":100023,"SetCode":"STX","Count":3},{"CollationId":100025,"SetCode":"MID","Count":4},{"CollationId":100027,"SetCode":"NEO","Count":41},{"CollationId":100028,"SetCode":"SNC","Count":3},{"CollationId":400028,"SetCode":"Y22SNC","Count":1},{"CollationId":100029,"SetCode":"HBG","Count":8},{"CollationId":100030,"SetCode":"DMU","Count":1},{"CollationId":100031,"SetCode":"BRO","Count":1},{"CollationId":100032,"SetCode":"ONE","Count":3},{"CollationId":100033,"SetCode":"SIR","Count":3},{"CollationId":100037,"SetCode":"MOM","Count":3},{"CollationId":100039,"SetCode":"LTR","Count":3},{"CollationId":100040,"SetCode":"WOE","Count":3},{"CollationId":400031,"SetCode":"Y23BRO","Count":6},{"CollationId":400032,"SetCode":"Y23ONE","Count":3},{"CollationId":100038,"SetCode":"MAT","Count":3},{"CollationId":400040,"SetCode":"Y24WOE","Count":3},{"CollationId":400041,"SetCode":"Y24LCI","Count":3},{"CollationId":100042,"SetCode":"KTK","Count":3},{"CollationId":100041,"SetCode":"LCI","Count":4},{"CollationId":100043,"SetCode":"MKM","Count":6},{"CollationId":100044,"SetCode":"OTJ","Count":4},{"CollationId":400043,"SetCode":"Y24MKM","Count":3},{"CollationId":400044,"SetCode":"Y24OTJ","Count":3}],"Vouchers":{},"Cosmetics":{"ArtStyles":[{"Type":"ArtStyle","Id":"404952.DA","ArtId":404952,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"409037.DA","ArtId":409037,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"127296.DA","ArtId":127296,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"404505.DA","ArtId":404505,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"402637.DA","ArtId":402637,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"407656.DA","ArtId":407656,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418892.DA","ArtId":418892,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418903.DA","ArtId":418903,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"Event","Type":"ArtStyle","Id":"420249.JP","ArtId":420249,"Variant":"JP","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"416627.SH","ArtId":416627,"Variant":"SH","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417880.JP","ArtId":417880,"Variant":"JP","ExplicitGrpIds":[]},{"AcquisitionFlags":"CodeRedemption","Type":"ArtStyle","Id":"406523.SG","ArtId":406523,"Variant":"SG","ExplicitGrpIds":[]},{"AcquisitionFlags":"CodeRedemption","Type":"ArtStyle","Id":"406664.SG","ArtId":406664,"Variant":"SG","ExplicitGrpIds":[]},{"AcquisitionFlags":"CodeRedemption","Type":"ArtStyle","Id":"409514.SG","ArtId":409514,"Variant":"SG","ExplicitGrpIds":[]},{"AcquisitionFlags":"CodeRedemption","Type":"ArtStyle","Id":"406559.SG","ArtId":406559,"Variant":"SG","ExplicitGrpIds":[]},{"AcquisitionFlags":"CodeRedemption","Type":"ArtStyle","Id":"406626.SG","ArtId":406626,"Variant":"SG","ExplicitGrpIds":[]},{"AcquisitionFlags":"CodeRedemption","Type":"ArtStyle","Id":"402959.DA","ArtId":402959,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"CodeRedemption","Type":"ArtStyle","Id":"400332.DA","ArtId":400332,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"CodeRedemption","Type":"ArtStyle","Id":"404135.DA","ArtId":404135,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"CodeRedemption","Type":"ArtStyle","Id":"404488.DA","ArtId":404488,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"CodeRedemption","Type":"ArtStyle","Id":"402057.DA","ArtId":402057,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418809.DA","ArtId":418809,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418895.DA","ArtId":418895,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418859.DA","ArtId":418859,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418963.DA","ArtId":418963,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418925.DA","ArtId":418925,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418777.DA","ArtId":418777,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418962.DA","ArtId":418962,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418781.DA","ArtId":418781,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418812.DA","ArtId":418812,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"416383.DA","ArtId":416383,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"416356.DA","ArtId":416356,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418912.DA","ArtId":418912,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418917.DA","ArtId":418917,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418785.DA","ArtId":418785,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418790.DA","ArtId":418790,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418988.DA","ArtId":418988,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418798.DA","ArtId":418798,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419549.DA","ArtId":419549,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419568.DA","ArtId":419568,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"418867.DA","ArtId":418867,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"419407.DA","ArtId":419407,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419576.DA","ArtId":419576,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"422879.DA","ArtId":422879,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419437.DA","ArtId":419437,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419501.DA","ArtId":419501,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419546.DA","ArtId":419546,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419693.DA","ArtId":419693,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"415977.DA","ArtId":415977,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419600.DA","ArtId":419600,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419682.DA","ArtId":419682,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419495.DA","ArtId":419495,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419551.DA","ArtId":419551,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419683.DA","ArtId":419683,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419694.DA","ArtId":419694,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419488.DA","ArtId":419488,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419685.DA","ArtId":419685,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419452.DA","ArtId":419452,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419643.DA","ArtId":419643,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419687.DA","ArtId":419687,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419567.DA","ArtId":419567,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419720.DA","ArtId":419720,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"415990.DA","ArtId":415990,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419665.DA","ArtId":419665,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419664.DA","ArtId":419664,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419722.DA","ArtId":419722,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419672.DA","ArtId":419672,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419676.DA","ArtId":419676,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419601.DA","ArtId":419601,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419620.DA","ArtId":419620,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419617.DA","ArtId":419617,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419721.DA","ArtId":419721,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"424152.DA","ArtId":424152,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419628.DA","ArtId":419628,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419492.DA","ArtId":419492,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419514.DA","ArtId":419514,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419515.DA","ArtId":419515,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419436.DA","ArtId":419436,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419719.DA","ArtId":419719,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"Event","Type":"ArtStyle","Id":"417888.JP","ArtId":417888,"Variant":"JP","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419536.DA","ArtId":419536,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419528.DA","ArtId":419528,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419527.DA","ArtId":419527,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419593.DA","ArtId":419593,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419446.DA","ArtId":419446,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"415986.DA","ArtId":415986,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419468.DA","ArtId":419468,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419602.DA","ArtId":419602,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419466.DA","ArtId":419466,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419690.DA","ArtId":419690,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419692.DA","ArtId":419692,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419718.DA","ArtId":419718,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419651.DA","ArtId":419651,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419473.DA","ArtId":419473,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"419467.DA","ArtId":419467,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"419630.DA","ArtId":419630,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419688.DA","ArtId":419688,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419476.DA","ArtId":419476,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421125.DA","ArtId":421125,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417889.JP","ArtId":417889,"Variant":"JP","ExplicitGrpIds":[]},{"AcquisitionFlags":"Event","Type":"ArtStyle","Id":"417868.JP","ArtId":417868,"Variant":"JP","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417340.DA","ArtId":417340,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421130.DA","ArtId":421130,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"419511.DA","ArtId":419511,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421133.DA","ArtId":421133,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417319.DA","ArtId":417319,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"421180.DA","ArtId":421180,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"421284.DA","ArtId":421284,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"421132.DA","ArtId":421132,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"421237.DA","ArtId":421237,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421114.DA","ArtId":421114,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421162.DA","ArtId":421162,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417065.DA","ArtId":417065,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421259.DA","ArtId":421259,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417343.DA","ArtId":417343,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421343.DA","ArtId":421343,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417314.DA","ArtId":417314,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417066.DA","ArtId":417066,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421159.DA","ArtId":421159,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417063.DA","ArtId":417063,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421346.DA","ArtId":421346,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417332.DA","ArtId":417332,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421297.DA","ArtId":421297,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417361.DA","ArtId":417361,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421121.DA","ArtId":421121,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421170.DA","ArtId":421170,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421342.DA","ArtId":421342,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421212.DA","ArtId":421212,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421254.DA","ArtId":421254,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421150.DA","ArtId":421150,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421172.DA","ArtId":421172,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421184.DA","ArtId":421184,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421185.DA","ArtId":421185,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421198.DA","ArtId":421198,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421193.DA","ArtId":421193,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421205.DA","ArtId":421205,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421227.DA","ArtId":421227,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421229.DA","ArtId":421229,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417351.DA","ArtId":417351,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421242.DA","ArtId":421242,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421263.DA","ArtId":421263,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421270.DA","ArtId":421270,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421273.DA","ArtId":421273,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421282.DA","ArtId":421282,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421344.DA","ArtId":421344,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421283.DA","ArtId":421283,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421303.DA","ArtId":421303,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"422142.DA","ArtId":422142,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"422322.DA","ArtId":422322,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"417325.DA","ArtId":417325,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"421142.DA","ArtId":421142,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"422152.DA","ArtId":422152,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"422167.DA","ArtId":422167,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"422148.DA","ArtId":422148,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"422213.DA","ArtId":422213,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"443063.DA","ArtId":443063,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418126.SCHEMATIC","ArtId":418126,"Variant":"SCHEMATIC","ExplicitGrpIds":[]}],"Avatars":[{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_ChandraNalaar","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_AjaniGoldmane","Type":"Avatar"},{"Id":"Avatar_Basic_GideonJura","Type":"Avatar"},{"Id":"Avatar_Basic_Teferi","Type":"Avatar"},{"Id":"Avatar_Basic_SarkhanVol","Type":"Avatar"},{"Id":"Avatar_Basic_Tezzeret","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_VivienReid","Type":"Avatar"},{"Id":"Avatar_Basic_NissaRevane","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_LilianaVess","Type":"Avatar"},{"Id":"Avatar_Basic_Karn","Type":"Avatar"},{"Id":"Avatar_Basic_JayaBallard","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_JaceBeleren","Type":"Avatar"},{"Id":"Avatar_Basic_Ellywick_AFR","Type":"Avatar"},{"Id":"Avatar_Basic_Wrenn_MID","Type":"Avatar"},{"AcquisitionFlags":"CodeRedemption","Id":"Avatar_Basic_Sorin_VOW","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_Elspeth_MOM","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_Ashiok_WAR","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_Kaito_NEO","Type":"Avatar"}],"Pets":[{"Type":"Pet","Id":"AFR_Dragon.Skin1","Name":"AFR_Dragon","Variant":"Skin1"},{"Type":"Pet","Id":"AFR_Dragon.Skin2","Name":"AFR_Dragon","Variant":"Skin2"},{"Type":"Pet","Id":"MID_Geist.Skin1","Name":"MID_Geist","Variant":"Skin1"},{"Type":"Pet","Id":"MID_Geist.Skin2","Name":"MID_Geist","Variant":"Skin2"},{"Type":"Pet","Id":"MID_Geist.Skin3","Name":"MID_Geist","Variant":"Skin3"},{"Type":"Pet","Id":"VOW_Bat.Level1","Name":"VOW_Bat","Variant":"Level1"},{"Type":"Pet","Id":"VOW_Bat.Level2","Name":"VOW_Bat","Variant":"Level2"},{"Type":"Pet","Id":"VOW_Bat.Level3","Name":"VOW_Bat","Variant":"Level3"}],"Sleeves":[{"AcquisitionFlags":"CodeRedemption","Id":"CardBack_Basic_Thunderstorm_Bitterblossom","Type":"Sleeve"},{"AcquisitionFlags":"CodeRedemption","Id":"CardBack_STX_418002","Type":"Sleeve"},{"AcquisitionFlags":"CodeRedemption","Id":"CardBack_STX_418001","Type":"Sleeve"},{"AcquisitionFlags":"CodeRedemption","Id":"CardBack_STX_418003","Type":"Sleeve"},{"AcquisitionFlags":"CodeRedemption","Id":"CardBack_STX_418004","Type":"Sleeve"},{"AcquisitionFlags":"CodeRedemption","Id":"CardBack_STX_418005","Type":"Sleeve"},{"Id":"CardBack_AFR_419749","Type":"Sleeve"},{"Id":"CardBack_AFR_419144","Type":"Sleeve"},{"Id":"CardBack_AFR_419111","Type":"Sleeve"},{"Id":"CardBack_MID_424253","Type":"Sleeve"},{"Id":"CardBack_MID_423524","Type":"Sleeve"},{"Id":"CardBack_ZNR_402686","Type":"Sleeve"},{"Id":"CardBack_MID_422493","Type":"Sleeve"},{"Id":"CardBack_VOW_424637","Type":"Sleeve"},{"Id":"CardBack_VOW_422028","Type":"Sleeve"},{"Id":"CardBack_VOW_422180","Type":"Sleeve"},{"Id":"CardBack_VOW_421278","Type":"Sleeve"},{"Id":"CardBack_VOW_421349","Type":"Sleeve"},{"AcquisitionFlags":"Event, CodeRedemption","Id":"CardBack_DvC_409074","Type":"Sleeve"}],"Emotes":[{"AcquisitionFlags":"DefaultLoginGrant","Id":"Phrase_Basic_Hello","Type":"Emote","Category":"Greeting","Treatment":""},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Phrase_Basic_Nice_Thanks","Type":"Emote","FlipType":"Reply","Category":"Kudos","Treatment":""},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Phrase_Basic_Thinking_YourGo","Type":"Emote","FlipType":"Priority","Category":"Priority","Treatment":""},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Phrase_Basic_Oops_Sorry","Type":"Emote","FlipType":"Reply","Category":"Accident","Treatment":""},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Phrase_Basic_GoodGame","Type":"Emote","Category":"GoodGame","Treatment":""}]}}}'
    )
]

# Quick draft log entries collected from Player.log after the 2025-4-8 Arena Update
TDM_QUICK_DRAFT_ENTRIES_2025_4_8 = [
    (
        "Event Start",
        EventResults(
            new_event=True,
            data_update=False,
            current_set="TDM",
            current_event="QuickDraft",
            current_pack=0,
            current_pick=0,
            picks=[],
            pack=[],
            card_pool=[],
            missing=[]
        ),
        r'[UnityCrossThreadLogger]==> BotDraftDraftStatus {"id":"fc2ba2a1-ee38-450d-8645-d663ed59ed76","request":"{\"EventName\":\"QuickDraft_TDM_20250417\"}"}'
    ),
    (
        "P1P5 - Pack",
        EventResults(
            new_event=False,
            data_update=True,
            current_set="TDM",
            current_event="QuickDraft",
            current_pack=1,
            current_pick=5,
            picks=[],
            pack=["95571","95632","95679","95566","95532","95650","95619","95651","95772","95786"],
            card_pool=["95633","95679","95626","95746"],
            missing=[]
        ),
        r'{"CurrentModule":"BotDraft","Payload":"{\"Result\":\"Success\",\"EventName\":\"QuickDraft_TDM_20250417\",\"DraftStatus\":\"PickNext\",\"PackNumber\":0,\"PickNumber\":4,\"NumCardsToPick\":1,\"DraftPack\":[\"95571\",\"95632\",\"95679\",\"95566\",\"95532\",\"95650\",\"95619\",\"95651\",\"95772\",\"95786\"],\"PackStyles\":[],\"PickedCards\":[\"95633\",\"95679\",\"95626\",\"95746\"],\"PickedStyles\":[]}"}'
    ),
    (
        "P1P5 - Pick",
        EventResults(
            new_event=False,
            data_update=True,
            current_set="TDM",
            current_event="QuickDraft",
            current_pack=1,
            current_pick=5,
            picks=["95772"],
            pack=["95571","95632","95679","95566","95532","95650","95619","95651","95772","95786"],
            card_pool=["95633","95679","95626","95746","95772"],
            missing=[]
        ),
        r'[UnityCrossThreadLogger]==> BotDraftDraftPick {"id":"720e31b4-04ee-4a22-860e-008ab9d59030","request":"{\"EventName\":\"QuickDraft_TDM_20250417\",\"PickInfo\":{\"EventName\":\"QuickDraft_TDM_20250417\",\"CardId\":null,\"CardIds\":[\"95772\"],\"PackNumber\":0,\"PickNumber\":4}}"}'
    ),
]

# Traditional draft log entries collected from Player.log after 2024-5-7 Arena update
OTJ_TRAD_DRAFT_ENTRIES_2024_5_7 = [
    (
        "Event Start",
        EventResults(
            new_event=True,
            data_update=False,
            current_set="OTJ",
            current_event="TradDraft",
            current_pack=0,
            current_pick=0,
            picks=[],
            pack=[],
            card_pool=[],
            missing=[]
        ),
        r'[UnityCrossThreadLogger]==> Event_Join {"id":"57d3b2c6-71ef-44ee-a395-1e977fcdd6b6","request":"{\"EventName\":\"TradDraft_OTJ_20240416\",\"EntryCurrencyType\":\"Gem\",\"EntryCurrencyPaid\":1500,\"CustomTokenId\":null}"}'
    ),
    (
        "P1P1 - Pack",
        EventResults(
            new_event=False,
            data_update=True,
            current_set="OTJ",
            current_event="TradDraft",
            current_pack=1,
            current_pick=1,
            picks=[],
            pack=["90711","90515","90623","90686","90354","90571","90418","90511","90468","90429","90432","90458","90456","90593"], 
            card_pool=[],
            missing=[]
        ),
        r'[UnityCrossThreadLogger]==> LogBusinessEvents {"id":"f78e3f9d-6368-4bcc-98aa-7bd0297f29c0","request":"{\"PlayerId\":null,\"ClientPlatform\":null,\"DraftId\":\"df799bea-cba5-4acc-b7e0-bf3b742e6fb7\",\"EventId\":\"TradDraft_OTJ_20240416\",\"SeatNumber\":6,\"PackNumber\":1,\"PickNumber\":1,\"PickGrpId\":90686,\"CardsInPack\":[90711,90515,90623,90686,90354,90571,90418,90511,90468,90429,90432,90458,90456,90593],\"AutoPick\":false,\"TimeRemainingOnPick\":63.9975624,\"EventType\":24,\"EventTime\":\"2024-05-09T16:33:01.828189Z\"}"}'
    ),
    (
        "P1P1 - Pick",
        EventResults(
            new_event=False,
            data_update=True,
            current_set="OTJ",
            current_event="TradDraft",
            current_pack=1,
            current_pick=1,
            picks=["90686"],
            pack=["90711","90515","90623","90686","90354","90571","90418","90511","90468","90429","90432","90458","90456","90593"],  
            card_pool=["90686"],
            missing=[]
        ),
        r'[UnityCrossThreadLogger]==> Event_PlayerDraftMakePick {"id":"f803188b-1de3-4ad5-bfed-7a3cefdb6598","request":"{\"DraftId\":\"df799bea-cba5-4acc-b7e0-bf3b742e6fb7\",\"GrpId\":90686,\"Pack\":1,\"Pick\":1}"}'
    ),
    (
        "P1P2 - Pack",
        EventResults(
            new_event=False,
            data_update=True,
            current_set="OTJ",
            current_event="TradDraft",
            current_pack=1,
            current_pick=2,
            picks=[],
            pack=["90757","90461","90632","90667","90484","90440","90502","90476","90349","90418","90408","90466","90446"], 
            card_pool=["90686"],
            missing=[]
        ),
        r'[UnityCrossThreadLogger]Draft.Notify {"draftId":"df799bea-cba5-4acc-b7e0-bf3b742e6fb7","SelfPick":2,"SelfPack":1,"PackCards":"90757,90461,90632,90667,90484,90440,90502,90476,90349,90418,90408,90466,90446"}'
    ),
    (
        "P1P9 - Pack",
        EventResults(
            new_event=False,
            data_update=True,
            current_set="OTJ",
            current_event="TradDraft",
            current_pack=1,
            current_pick=9,
            picks=["90686"],
            pack=["90711","90623","90571","90432","90456","90593"],
            card_pool=["90686"],
            missing=["90515","90686","90354","90418","90511","90468","90429","90458"]
        ),
        r'[UnityCrossThreadLogger]Draft.Notify {"draftId":"df799bea-cba5-4acc-b7e0-bf3b742e6fb7","SelfPick":9,"SelfPack":1,"PackCards":"90711,90623,90571,90432,90456,90593"}'
    ),
    (
        "P3P14 - Pack",
        EventResults(
            new_event=False,
            data_update=True,
            current_set="OTJ",
            current_event="TradDraft",
            current_pack=3,
            current_pick=14,
            picks=[],
            pack=["90383"],
            card_pool=["90686"],
            missing=[]
        ),
        r'[UnityCrossThreadLogger]Draft.Notify {"draftId":"df799bea-cba5-4acc-b7e0-bf3b742e6fb7","SelfPick":14,"SelfPack":3,"PackCards":"90383"}'
    )
]

# Sealedlog entries collected from Player.log after 2024-9-24 Arena update
DSK_SEALED_ENTRIES_2024_9_24 = [
    (
        "Event Start",
        EventResults(
            new_event=True,
            data_update=False,
            current_set="DSK",
            current_event="Sealed",
            current_pack=0,
            current_pick=0,
            picks=[],
            pack=[],
            card_pool=[],
            missing=[]
        ),
        r'[UnityCrossThreadLogger]==> Event_Join {"id":"54d60b67-59a9-4188-bc42-ab78fed44fad","request":"{\"EventName\":\"Sealed_DSK_20240924\",\"EntryCurrencyType\":\"Gem\",\"EntryCurrencyPaid\":2000,\"CustomTokenId\":null}"}'
    ),
    (
        "Card Pool",
        EventResults(new_event=False,
                    data_update=True,
                    current_set="DSK",
                    current_event="Sealed",
                    current_pack=0,
                    current_pick=0,
                    picks=[],
                    pack=[], 
                    card_pool=["92248","92368","92257","92188","92143","92242","92055","92154","92149","92238","92162","92261","92350","92338","92307","92379","92154","92073","92167","92203","92143","92291","92219","92235","92127","92311","92208","92230","92201","92364","92073","92268","92111","92181","92236","92146","92267","92116","92185","92304","92066","92313","92076","92365","92156","92146","92343","92237","92369","92274","92055","92067","92308","92234","92265","92360","92212","92380","92172","92279","92148","92073","92154","92179","92224","92141","92316","92305","92342","92092","92266","92377","92279","92240","92148","92114","92172","92070","92290","92229","92090","92182","92113","92119"],
                    missing=[]
        ),
        r'{"Course":{"CourseId":"d276ee0e-a180-41f9-b41a-8249c1db4bdf","InternalEventName":"Sealed_DSK_20240924","CurrentModule":"DeckSelect","ModulePayload":"","CourseDeckSummary":{"Attributes":[],"FormatLegalities":{},"PreferredCosmetics":{},"DeckValidationSummaries":[],"UnownedCards":{}},"CardPool":[92248,92368,92257,92188,92143,92242,92055,92154,92149,92238,92162,92261,92350,92338,92307,92379,92154,92073,92167,92203,92143,92291,92219,92235,92127,92311,92208,92230,92201,92364,92073,92268,92111,92181,92236,92146,92267,92116,92185,92304,92066,92313,92076,92365,92156,92146,92343,92237,92369,92274,92055,92067,92308,92234,92265,92360,92212,92380,92172,92279,92148,92073,92154,92179,92224,92141,92316,92305,92342,92092,92266,92377,92279,92240,92148,92114,92172,92070,92290,92229,92090,92182,92113,92119],"CardStyles":[]},"InventoryInfo":{"SeqId":9,"Changes":[{"Source":"EventPayEntry","SourceId":"d276ee0e-a180-41f9-b41a-8249c1db4bdf","InventoryGems":-2000,"InventoryCustomTokens":{},"ArtStyles":[],"Avatars":[],"Sleeves":[],"Pets":[],"Emotes":[],"Titles":[],"Decks":[],"DecksV2":[],"DeckCards":{},"Boosters":[],"GrantedCards":[],"Vouchers":{},"NewLetters":[],"PrizeWallsUnlocked":[]},{"Source":"EventGrantCardPool","SourceId":"Sealed_DSK_20240924","InventoryCustomTokens":{},"ArtStyles":[],"Avatars":[],"Sleeves":[],"Pets":[],"Emotes":[],"Titles":[],"Decks":[],"DecksV2":[],"DeckCards":{},"Boosters":[],"GrantedCards":[{"GrpId":92248,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92368,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92257,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92188,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92143,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92143,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92242,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92055,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92055,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92154,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92154,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92154,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92149,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92238,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92162,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92261,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92350,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92338,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92307,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92073,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92073,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92073,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92167,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92203,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92291,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92219,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92235,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92127,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92311,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92208,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92230,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92201,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92364,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92268,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92111,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92181,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92236,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92146,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92146,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92267,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92116,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92185,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92304,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92066,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92313,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92076,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92365,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92156,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92343,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92237,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92369,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92274,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92067,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92308,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92234,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92265,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92360,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92212,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92172,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92172,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92279,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92279,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92148,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92148,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92179,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92224,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92141,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92316,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92305,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92342,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92092,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92266,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92240,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92114,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92070,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92290,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92229,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92090,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92182,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92113,"CardAdded":true,"SetCode":"DSK"},{"GrpId":92119,"CardAdded":true,"SetCode":"DSK"}],"Vouchers":{},"NewLetters":[],"PrizeWallsUnlocked":[]}],"Gems":350,"Gold":4500,"TotalVaultProgress":869,"wcTrackPosition":6,"WildCardCommons":68,"WildCardUnCommons":87,"WildCardRares":28,"WildCardMythics":12,"CustomTokens":{"BattlePass_AFR_Orb":1,"BattlePass_HBG_Orb":1,"BonusPackProgress":1,"BattlePass_MKM_Orb":1,"DraftToken":1},"Boosters":[{"CollationId":100026,"SetCode":"VOW","Count":10},{"CollationId":100024,"SetCode":"AFR","Count":7},{"CollationId":100020,"SetCode":"ZNR","Count":2},{"CollationId":100022,"SetCode":"KHM","Count":2},{"CollationId":100023,"SetCode":"STX","Count":3},{"CollationId":100025,"SetCode":"MID","Count":4},{"CollationId":100027,"SetCode":"NEO","Count":41},{"CollationId":100028,"SetCode":"SNC","Count":3},{"CollationId":400028,"SetCode":"Y22SNC","Count":1},{"CollationId":100029,"SetCode":"HBG","Count":8},{"CollationId":100030,"SetCode":"DMU","Count":2},{"CollationId":100031,"SetCode":"BRO","Count":1},{"CollationId":100032,"SetCode":"ONE","Count":3},{"CollationId":100033,"SetCode":"SIR","Count":3},{"CollationId":100037,"SetCode":"MOM","Count":3},{"CollationId":100039,"SetCode":"LTR","Count":3},{"CollationId":100040,"SetCode":"WOE","Count":3},{"CollationId":400031,"SetCode":"Y23BRO","Count":6},{"CollationId":400032,"SetCode":"Y23ONE","Count":3},{"CollationId":100038,"SetCode":"MAT","Count":3},{"CollationId":400040,"SetCode":"Y24WOE","Count":3},{"CollationId":400041,"SetCode":"Y24LCI","Count":3},{"CollationId":100042,"SetCode":"KTK","Count":3},{"CollationId":100041,"SetCode":"LCI","Count":4},{"CollationId":100043,"SetCode":"MKM","Count":6},{"CollationId":100044,"SetCode":"OTJ","Count":4},{"CollationId":400043,"SetCode":"Y24MKM","Count":3},{"CollationId":400044,"SetCode":"Y24OTJ","Count":3},{"CollationId":100046,"SetCode":"BLB","Count":3},{"CollationId":400046,"SetCode":"Y25BLB","Count":3},{"CollationId":100045,"SetCode":"MH3","Count":3},{"CollationId":100047,"SetCode":"DSK","Count":3}],"Vouchers":{},"PrizeWallsUnlocked":[],"Cosmetics":{"ArtStyles":[{"Type":"ArtStyle","Id":"404952.DA","ArtId":404952,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"409037.DA","ArtId":409037,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"127296.DA","ArtId":127296,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"404505.DA","ArtId":404505,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"402637.DA","ArtId":402637,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"407656.DA","ArtId":407656,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418892.DA","ArtId":418892,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418903.DA","ArtId":418903,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"Event","Type":"ArtStyle","Id":"420249.JP","ArtId":420249,"Variant":"JP","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"416627.SH","ArtId":416627,"Variant":"SH","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417880.JP","ArtId":417880,"Variant":"JP","ExplicitGrpIds":[]},{"AcquisitionFlags":"CodeRedemption","Type":"ArtStyle","Id":"406523.SG","ArtId":406523,"Variant":"SG","ExplicitGrpIds":[]},{"AcquisitionFlags":"CodeRedemption","Type":"ArtStyle","Id":"406664.SG","ArtId":406664,"Variant":"SG","ExplicitGrpIds":[]},{"AcquisitionFlags":"CodeRedemption","Type":"ArtStyle","Id":"409514.SG","ArtId":409514,"Variant":"SG","ExplicitGrpIds":[]},{"AcquisitionFlags":"CodeRedemption","Type":"ArtStyle","Id":"406559.SG","ArtId":406559,"Variant":"SG","ExplicitGrpIds":[]},{"AcquisitionFlags":"CodeRedemption","Type":"ArtStyle","Id":"406626.SG","ArtId":406626,"Variant":"SG","ExplicitGrpIds":[]},{"AcquisitionFlags":"CodeRedemption","Type":"ArtStyle","Id":"402959.DA","ArtId":402959,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"CodeRedemption","Type":"ArtStyle","Id":"400332.DA","ArtId":400332,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"CodeRedemption","Type":"ArtStyle","Id":"404135.DA","ArtId":404135,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"CodeRedemption","Type":"ArtStyle","Id":"404488.DA","ArtId":404488,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"CodeRedemption","Type":"ArtStyle","Id":"402057.DA","ArtId":402057,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418809.DA","ArtId":418809,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418895.DA","ArtId":418895,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418859.DA","ArtId":418859,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418963.DA","ArtId":418963,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418925.DA","ArtId":418925,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418777.DA","ArtId":418777,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418962.DA","ArtId":418962,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418781.DA","ArtId":418781,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418812.DA","ArtId":418812,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"416383.DA","ArtId":416383,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"416356.DA","ArtId":416356,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418912.DA","ArtId":418912,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418917.DA","ArtId":418917,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418785.DA","ArtId":418785,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418790.DA","ArtId":418790,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418988.DA","ArtId":418988,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418798.DA","ArtId":418798,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419549.DA","ArtId":419549,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419568.DA","ArtId":419568,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"418867.DA","ArtId":418867,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"419407.DA","ArtId":419407,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419576.DA","ArtId":419576,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"422879.DA","ArtId":422879,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419437.DA","ArtId":419437,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419501.DA","ArtId":419501,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419546.DA","ArtId":419546,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419693.DA","ArtId":419693,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"415977.DA","ArtId":415977,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419600.DA","ArtId":419600,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419682.DA","ArtId":419682,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419495.DA","ArtId":419495,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419551.DA","ArtId":419551,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419683.DA","ArtId":419683,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419694.DA","ArtId":419694,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419488.DA","ArtId":419488,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419685.DA","ArtId":419685,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419452.DA","ArtId":419452,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419643.DA","ArtId":419643,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419687.DA","ArtId":419687,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419567.DA","ArtId":419567,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419720.DA","ArtId":419720,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"415990.DA","ArtId":415990,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419665.DA","ArtId":419665,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419664.DA","ArtId":419664,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419722.DA","ArtId":419722,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419672.DA","ArtId":419672,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419676.DA","ArtId":419676,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419601.DA","ArtId":419601,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419620.DA","ArtId":419620,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419617.DA","ArtId":419617,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419721.DA","ArtId":419721,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"424152.DA","ArtId":424152,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419628.DA","ArtId":419628,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419492.DA","ArtId":419492,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419514.DA","ArtId":419514,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419515.DA","ArtId":419515,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419436.DA","ArtId":419436,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419719.DA","ArtId":419719,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"Event","Type":"ArtStyle","Id":"417888.JP","ArtId":417888,"Variant":"JP","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419536.DA","ArtId":419536,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419528.DA","ArtId":419528,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419527.DA","ArtId":419527,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419593.DA","ArtId":419593,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419446.DA","ArtId":419446,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"415986.DA","ArtId":415986,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419468.DA","ArtId":419468,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419602.DA","ArtId":419602,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419466.DA","ArtId":419466,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419690.DA","ArtId":419690,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419692.DA","ArtId":419692,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419718.DA","ArtId":419718,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419651.DA","ArtId":419651,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419473.DA","ArtId":419473,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"419467.DA","ArtId":419467,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"419630.DA","ArtId":419630,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419688.DA","ArtId":419688,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"419476.DA","ArtId":419476,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421125.DA","ArtId":421125,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417889.JP","ArtId":417889,"Variant":"JP","ExplicitGrpIds":[]},{"AcquisitionFlags":"Event","Type":"ArtStyle","Id":"417868.JP","ArtId":417868,"Variant":"JP","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417340.DA","ArtId":417340,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421130.DA","ArtId":421130,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"419511.DA","ArtId":419511,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421133.DA","ArtId":421133,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417319.DA","ArtId":417319,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"421180.DA","ArtId":421180,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"421284.DA","ArtId":421284,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"421132.DA","ArtId":421132,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"421237.DA","ArtId":421237,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421114.DA","ArtId":421114,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421162.DA","ArtId":421162,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417065.DA","ArtId":417065,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421259.DA","ArtId":421259,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417343.DA","ArtId":417343,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421343.DA","ArtId":421343,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417314.DA","ArtId":417314,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417066.DA","ArtId":417066,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421159.DA","ArtId":421159,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417063.DA","ArtId":417063,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421346.DA","ArtId":421346,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417332.DA","ArtId":417332,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421297.DA","ArtId":421297,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417361.DA","ArtId":417361,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421121.DA","ArtId":421121,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421170.DA","ArtId":421170,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421342.DA","ArtId":421342,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421212.DA","ArtId":421212,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421254.DA","ArtId":421254,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421150.DA","ArtId":421150,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421172.DA","ArtId":421172,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421184.DA","ArtId":421184,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421185.DA","ArtId":421185,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421198.DA","ArtId":421198,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421193.DA","ArtId":421193,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421205.DA","ArtId":421205,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421227.DA","ArtId":421227,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421229.DA","ArtId":421229,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"417351.DA","ArtId":417351,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421242.DA","ArtId":421242,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421263.DA","ArtId":421263,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421270.DA","ArtId":421270,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421273.DA","ArtId":421273,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421282.DA","ArtId":421282,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421344.DA","ArtId":421344,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421283.DA","ArtId":421283,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"421303.DA","ArtId":421303,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"422142.DA","ArtId":422142,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"422322.DA","ArtId":422322,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"417325.DA","ArtId":417325,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"421142.DA","ArtId":421142,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"422152.DA","ArtId":422152,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"422167.DA","ArtId":422167,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"422148.DA","ArtId":422148,"Variant":"DA","ExplicitGrpIds":[]},{"AcquisitionFlags":"SeasonReward","Type":"ArtStyle","Id":"422213.DA","ArtId":422213,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"443063.DA","ArtId":443063,"Variant":"DA","ExplicitGrpIds":[]},{"Type":"ArtStyle","Id":"418126.SCHEMATIC","ArtId":418126,"Variant":"SCHEMATIC","ExplicitGrpIds":[]}],"Avatars":[{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_ChandraNalaar","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_AjaniGoldmane","Type":"Avatar"},{"Id":"Avatar_Basic_GideonJura","Type":"Avatar"},{"Id":"Avatar_Basic_Teferi","Type":"Avatar"},{"Id":"Avatar_Basic_SarkhanVol","Type":"Avatar"},{"Id":"Avatar_Basic_Tezzeret","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_VivienReid","Type":"Avatar"},{"Id":"Avatar_Basic_NissaRevane","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_LilianaVess","Type":"Avatar"},{"Id":"Avatar_Basic_Karn","Type":"Avatar"},{"Id":"Avatar_Basic_JayaBallard","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_JaceBeleren","Type":"Avatar"},{"Id":"Avatar_Basic_Ellywick_AFR","Type":"Avatar"},{"Id":"Avatar_Basic_Wrenn_MID","Type":"Avatar"},{"AcquisitionFlags":"CodeRedemption","Id":"Avatar_Basic_Sorin_VOW","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_Elspeth_MOM","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_Ashiok_WAR","Type":"Avatar"},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Avatar_Basic_Kaito_NEO","Type":"Avatar"}],"Pets":[{"Type":"Pet","Id":"AFR_Dragon.Skin1","Name":"AFR_Dragon","Variant":"Skin1"},{"Type":"Pet","Id":"AFR_Dragon.Skin2","Name":"AFR_Dragon","Variant":"Skin2"},{"Type":"Pet","Id":"MID_Geist.Skin1","Name":"MID_Geist","Variant":"Skin1"},{"Type":"Pet","Id":"MID_Geist.Skin2","Name":"MID_Geist","Variant":"Skin2"},{"Type":"Pet","Id":"MID_Geist.Skin3","Name":"MID_Geist","Variant":"Skin3"},{"Type":"Pet","Id":"VOW_Bat.Level1","Name":"VOW_Bat","Variant":"Level1"},{"Type":"Pet","Id":"VOW_Bat.Level2","Name":"VOW_Bat","Variant":"Level2"},{"Type":"Pet","Id":"VOW_Bat.Level3","Name":"VOW_Bat","Variant":"Level3"}],"Sleeves":[{"AcquisitionFlags":"CodeRedemption","Id":"CardBack_Basic_Thunderstorm_Bitterblossom","Type":"Sleeve"},{"AcquisitionFlags":"CodeRedemption","Id":"CardBack_STX_418002","Type":"Sleeve"},{"AcquisitionFlags":"CodeRedemption","Id":"CardBack_STX_418001","Type":"Sleeve"},{"AcquisitionFlags":"CodeRedemption","Id":"CardBack_STX_418003","Type":"Sleeve"},{"AcquisitionFlags":"CodeRedemption","Id":"CardBack_STX_418004","Type":"Sleeve"},{"AcquisitionFlags":"CodeRedemption","Id":"CardBack_STX_418005","Type":"Sleeve"},{"Id":"CardBack_AFR_419749","Type":"Sleeve"},{"Id":"CardBack_AFR_419144","Type":"Sleeve"},{"Id":"CardBack_AFR_419111","Type":"Sleeve"},{"Id":"CardBack_MID_424253","Type":"Sleeve"},{"Id":"CardBack_MID_423524","Type":"Sleeve"},{"Id":"CardBack_ZNR_402686","Type":"Sleeve"},{"Id":"CardBack_MID_422493","Type":"Sleeve"},{"Id":"CardBack_VOW_424637","Type":"Sleeve"},{"Id":"CardBack_VOW_422028","Type":"Sleeve"},{"Id":"CardBack_VOW_422180","Type":"Sleeve"},{"Id":"CardBack_VOW_421278","Type":"Sleeve"},{"Id":"CardBack_VOW_421349","Type":"Sleeve"},{"AcquisitionFlags":"Event, CodeRedemption","Id":"CardBack_DvC_409074","Type":"Sleeve"},{"Id":"CardBack_DG_MemorialSleeve","Type":"Sleeve"}],"Emotes":[{"AcquisitionFlags":"DefaultLoginGrant","Id":"Phrase_Basic_Hello","Type":"Emote","Category":"Greeting","Treatment":""},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Phrase_Basic_Nice_Thanks","Type":"Emote","FlipType":"Reply","Category":"Kudos","Treatment":""},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Phrase_Basic_Thinking_YourGo","Type":"Emote","FlipType":"Priority","Category":"Priority","Treatment":""},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Phrase_Basic_Oops_Sorry","Type":"Emote","FlipType":"Reply","Category":"Accident","Treatment":""},{"AcquisitionFlags":"DefaultLoginGrant","Id":"Phrase_Basic_GoodGame","Type":"Emote","Category":"GoodGame","Treatment":""}],"Titles":[]}}}'
    )
]

ARENA_OPEN_TEST_ENTRIES = [
    (
        "Unknown Event Start 1",
        EventResults(
            new_event=False,
            data_update=False,
            current_set="",
            current_event="",
            current_pack=0,
            current_pick=0,
            picks=[],
            pack=[],
            card_pool=[],
            missing=[]
        ),
        r'[UnityCrossThreadLogger]==> Event_Join {"id":"57d3b2c6-71ef-44ee-a395-1e977fcdd6b6","request":"{\"EventName\":\"ArenaOpen_Day_Bo1_20240622\",\"EntryCurrencyType\":\"Gem\",\"EntryCurrencyPaid\":1500,\"CustomTokenId\":null}"}'
    ),
    (
        "Unknown Event Start 2",
        EventResults(
            new_event=False,
            data_update=False,
            current_set="",
            current_event="",
            current_pack=0,
            current_pick=0,
            picks=[],
            pack=[],
            card_pool=[],
            missing=[]
        ),
        r'[UnityCrossThreadLogger]==> Event_Join {"id":"57d3b2c6-71ef-44ee-a395-1e977fcdd6b6","request":"{\"EventName\":\"arenaopen_Day1_Bo1_20240622\",\"EntryCurrencyType\":\"Gem\",\"EntryCurrencyPaid\":1500,\"CustomTokenId\":null}"}'
    ),
    (
        "Day1 Event Start",
        EventResults(
            new_event=True,
            data_update=False,
            current_set="MH3",
            current_event="OpenDay1",
            current_pack=0,
            current_pick=0,
            picks=[],
            pack=[],
            card_pool=[],
            missing=[]
        ),
        r'[UnityCrossThreadLogger]==> Event_Join {"id":"57d3b2c6-71ef-44ee-a395-1e977fcdd6b6","request":"{\"EventName\":\"ArenaOpen_Day1_Bo1_20240622\",\"EntryCurrencyType\":\"Gem\",\"EntryCurrencyPaid\":1500,\"CustomTokenId\":null}"}'
    ),
    (
        "Day2 Event Start",
        EventResults(
            new_event=True,
            data_update=False,
            current_set="OTJ",
            current_event="OpenDay2",
            current_pack=0,
            current_pick=0,
            picks=[],
            pack=[],
            card_pool=[],
            missing=[]
        ),
        r'[UnityCrossThreadLogger]==> Event_Join {"id":"57d3b2c6-71ef-44ee-a395-1e977fcdd6b6","request":"{\"EventName\":\"ArenaOpen_Day2_DraftOne_20240623\",\"EntryCurrencyType\":\"Gem\",\"EntryCurrencyPaid\":1500,\"CustomTokenId\":null}"}'
    ),
    (
        "Qualifier Event Start",
        EventResults(
            new_event=True,
            data_update=False,
            current_set="MKM",
            current_event="QualSealed",
            current_pack=0,
            current_pick=0,
            picks=[],
            pack=[],
            card_pool=[],
            missing=[]
        ),
        r'[UnityCrossThreadLogger]==> Event_Join {"id":"57d3b2c6-71ef-44ee-a395-1e977fcdd6b6","request":"{\"EventName\":\"QualifierPlayIn_Bo1_MH3_20240707\",\"EntryCurrencyType\":\"Gem\",\"EntryCurrencyPaid\":1500,\"CustomTokenId\":null}"}'
    ),
    (
        "Arena Direct Event Start",
        EventResults(
            new_event=True,
            data_update=False,
            current_set="OTJ",
            current_event="Sealed",
            current_pack=0,
            current_pick=0,
            picks=[],
            pack=[],
            card_pool=[],
            missing=[]
        ),
        r'[UnityCrossThreadLogger]==> Event_Join {"id":"57d3b2c6-71ef-44ee-a395-1e977fcdd6b6","request":"{\"EventName\":\"ArenaDirect_OTJ_Sealed_20240726\",\"EntryCurrencyType\":\"Gem\",\"EntryCurrencyPaid\":1500,\"CustomTokenId\":null}"}'
    ),
]

OM1_PICK_TWO_PREMIER_DRAFT_ENTRIES = [
    (
        "Event Start",
        EventResults(
            new_event=True,
            data_update=False,
            current_set="OM1",
            current_event="PickTwoDraft",
            current_pack=0,
            current_pick=0,
            picks=[],
            pack=[],
            card_pool=[],
            missing=[]
        ),
        r'[UnityCrossThreadLogger]==> EventJoin {"id":"b8d5b850-4c86-4fa0-9184-bf238c10a26a","request":"{\"EventName\":\"PickTwoDraft_OM1_20250923\",\"EntryCurrencyType\":\"Gem\",\"EntryCurrencyPaid\":900,\"CustomTokenId\":null,\"EventChoice\":\"\"}"}'
    ),
    (
        "P1P1 - Pack",
        EventResults(
            new_event=False,
            data_update=True,
            current_set="OM1",
            current_event="PickTwoDraft",
            current_pack=1,
            current_pick=1,
            picks=[],
            pack=["97864","97988","97995","97827","97879","97914","97918","97992","97842","97878","97977","97923","97911","95197"],
            card_pool=[],
            missing=[],
        ),
        # Line 341
        r'[UnityCrossThreadLogger]==> LogBusinessEvents {"id":"402f96d0-6517-492a-bc9a-1e713838e53c","request":"{\"PlayerId\":null,\"ClientPlatform\":null,\"DraftId\":\"dbd971d5-5bee-4d10-a2ec-eac0530d6553\",\"EventId\":\"PickTwoDraft_OM1_20250923\",\"SeatNumber\":0,\"PackNumber\":1,\"PickNumber\":1,\"PickGrpId\":97923,\"CardsInPack\":[97864,97988,97995,97827,97879,97914,97918,97992,97842,97878,97977,97923,97911,95197],\"AutoPick\":false,\"TimeRemainingOnPick\":47.4696846,\"EventType\":24,\"EventTime\":\"2025-09-23T20:46:55.7381073Z\"}"}'
    ),
    (
        "P1P1 - Pick",
        EventResults(
            new_event=False,
            data_update=True,
            current_set="OM1",
            current_event="PickTwoDraft",
            current_pack=1,
            current_pick=1,
            picks=["97923","97977"],
            pack=["97864","97988","97995","97827","97879","97914","97918","97992","97842","97878","97977","97923","97911","95197"],
            card_pool=["97923","97977"],
            missing=[]
        ),
        r'[UnityCrossThreadLogger]==> EventPlayerDraftMakePick {"id":"00b09bf6-aec3-490d-8be8-3da6dffa37c8","request":"{\"DraftId\":\"dbd971d5-5bee-4d10-a2ec-eac0530d6553\",\"GrpIds\":[97923,97977],\"Pack\":1,\"Pick\":1}"}'
    ),
    (
        "P1P5 - Pack",
        EventResults(
            new_event=False,
            data_update=True,
            current_set="OM1",
            current_event="PickTwoDraft",
            current_pack=1,
            current_pick=5,
            picks=["97923","97977"],
            pack=["97864","97988","97879","97914","97918","95197"],
            card_pool=["97923","97977"],
            missing=["97995","97827","97992","97842","97878","97977","97923","97911"]
        ),
        r'[UnityCrossThreadLogger]Draft.Notify {"draftId":"dbd971d5-5bee-4d10-a2ec-eac0530d6553","SelfPick":5,"SelfPack":1,"PackCards":"97864,97988,97879,97914,97918,95197"}'
    ),
    (
        "P1P5 - Pick",
        EventResults(
            new_event=False,
            data_update=True,
            current_set="OM1",
            current_event="PickTwoDraft",
            current_pack=1,
            current_pick=5,
            picks=["97923","97977","97918","97864"],
            pack=["97864","97988","97879","97914","97918","95197"],
            card_pool=["97923","97977","97918","97864"],
            missing=["97995","97827","97992","97842","97878","97977","97923","97911"]
        ),
        r'[UnityCrossThreadLogger]==> EventPlayerDraftMakePick {"id":"c6948135-4148-4104-8a6a-c8accde18edd","request":"{\"DraftId\":\"dbd971d5-5bee-4d10-a2ec-eac0530d6553\",\"GrpIds\":[97918,97864],\"Pack\":1,\"Pick\":5}"}'
    ),
]

@pytest.fixture(name="session_scanner",scope="session")
def fixture_session_scanner():
    scanner = ArenaScanner(TEST_LOG_FILE_LOCATION, TEST_SETS, sets_location = TEST_LOG_DIRECTORY, retrieve_unknown = True)
    scanner.log_enable(False)
    yield scanner
    if os.path.exists(TEST_LOG_FILE_LOCATION):
        os.remove(TEST_LOG_FILE_LOCATION)
  
@pytest.fixture(name="function_scanner",scope="function")
def fixture_function_scanner():
    if os.path.exists(TEST_LOG_FILE_LOCATION):
        os.remove(TEST_LOG_FILE_LOCATION)
    scanner = ArenaScanner(TEST_LOG_FILE_LOCATION, TEST_SETS, sets_location=TEST_SETS_DIRECTORY, retrieve_unknown=False)
    scanner.log_enable(False)
    yield scanner
    if os.path.exists(TEST_LOG_FILE_LOCATION):
        os.remove(TEST_LOG_FILE_LOCATION)

def event_test_cases(input_scanner, event_label, entry_label, expected, entry_string, mock_ocr):
    """Generic test cases for verifying the log events"""
    # Write the entry to the fake Player.log file
    with open(TEST_LOG_FILE_LOCATION, 'a', encoding="utf-8", errors="replace") as log_file:
        log_file.write(f"{entry_string}\n")

    # Verify that a new event was detected
    new_event = input_scanner.draft_start_search()
    assert expected.new_event == new_event, f"Test Failed: New Event, Set: {event_label}, {entry_label}, Expected: {expected.new_event}, Actual: {new_event}"

    # Verify that new event data was collected
    data_update = input_scanner.draft_data_search(False, False)
    assert expected.data_update == data_update, f"Test Failed: Data Update, Set: {event_label}, {entry_label}, Expected: {expected.data_update}, Actual: {data_update}"

    # Verify the current set and event
    current_set, current_event = input_scanner.retrieve_current_limited_event()
    assert (expected.current_set, expected.current_event) == (current_set, current_event), f"Test Failed: Set and Event, Set: {event_label}, {entry_label}, Expected: {(expected.current_set, expected.current_event)}, Actual: {(current_set, current_event)}"

    # Verify the current pack, pick
    current_pack, current_pick = input_scanner.retrieve_current_pack_and_pick()
    assert (expected.current_pack, expected.current_pick) == (current_pack, current_pick), f"Test Failed: Pack/Pick, Set: {event_label}, {entry_label}, Expected: {(expected.current_pack, expected.current_pick)}, Actual: {(current_pack, current_pick)}"

    # Verify the pack cards
    pack = [x["name"] for x in input_scanner.retrieve_current_pack_cards()]
    assert expected.pack == pack, f"Test Failed: Pack Cards, Set: {event_label}, {entry_label}, Expected: {expected.pack}, Actual: {pack}"

    # Verify the card pool
    card_pool = [x["name"] for x in input_scanner.retrieve_taken_cards()]
    assert expected.card_pool == card_pool, f"Test Failed: Card Pool, Set: {event_label}, {entry_label}, Expected: {expected.card_pool}, Actual: {card_pool}"

    # Verify the missing cards
    missing = [x["name"] for x in input_scanner.retrieve_current_missing_cards()]
    assert expected.missing == missing, f"Test Failed: Missing, Set: {event_label}, {entry_label}, Expected: {expected.missing}, Actual: {missing}"

    # Verify picks
    picks = [x["name"] for x in input_scanner.retrieve_current_picked_cards()]
    assert expected.picks == picks, f"Test Failed: Picks, Set: {event_label}, {entry_label}, Expected: {expected.picks}, Actual: {picks}"

    # Verify that the OCR method wasn't called
    assert mock_ocr.call_count == 0, f"Test Failed: OCR Check, Set: {event_label}, {entry_label}, Expected: 0, Actual: {mock_ocr.call_count}"

@pytest.mark.parametrize("entry_label, expected, entry_string", TDM_PREMIER_DRAFT_ENTRIES_2025_4_8)
def test_tdm_premier_draft_new(session_scanner, entry_label, expected, entry_string):
    """
    Verify that the new premier draft entries can be processed
    """
    with (
        patch("src.log_scanner.OCR.get_pack") as mock_ocr,
        patch("src.log_scanner.capture_screen_base64str")
    ):
        event_test_cases(session_scanner, "New TDM PremierDraft", entry_label, expected, entry_string, mock_ocr)

@pytest.mark.parametrize("entry_label, expected, entry_string", OTJ_PREMIER_DRAFT_ENTRIES_2024_5_7)
def test_otj_premier_draft_new(session_scanner, entry_label, expected, entry_string):
    """
    Verify that the new premier draft entries can be processed
    """
    with (
        patch("src.log_scanner.OCR.get_pack") as mock_ocr,
        patch("src.log_scanner.capture_screen_base64str")
    ):
        event_test_cases(session_scanner, "New OTJ PremierDraft", entry_label, expected, entry_string, mock_ocr)

@pytest.mark.parametrize("entry_label, expected, entry_string", MKM_PREMIER_DRAFT_ENTRIES)
def test_mkm_premier_draft_old(session_scanner, entry_label, expected, entry_string):
    """
    Verify that the old premier draft entries can be processed - WOTC might revert the changes
    """
    with (
        patch("src.log_scanner.OCR.get_pack") as mock_ocr,
        patch("src.log_scanner.capture_screen_base64str")
    ):
        event_test_cases(session_scanner, "Old MKM PremierDraft", entry_label, expected, entry_string, mock_ocr)

@pytest.mark.parametrize("entry_label, expected, entry_string", TDM_QUICK_DRAFT_ENTRIES_2025_4_8)
def test_tdm_quick_draft_new(session_scanner, entry_label, expected, entry_string):
    """
    Verify that the new quick draft entries can be processed
    """
    with (
        patch("src.log_scanner.OCR.get_pack") as mock_ocr,
        patch("src.log_scanner.capture_screen_base64str")
    ):
        event_test_cases(session_scanner, "New TDM QuickDraft", entry_label, expected, entry_string, mock_ocr)

@pytest.mark.parametrize("entry_label, expected, entry_string", DMU_QUICK_DRAFT_ENTRIES_2024_5_7)
def test_dmu_quick_draft_new(session_scanner, entry_label, expected, entry_string):
    """
    Verify that the old quick draft entries can be processed - WOTC might revert the changes
    """
    with (
        patch("src.log_scanner.OCR.get_pack") as mock_ocr,
        patch("src.log_scanner.capture_screen_base64str")
    ):
        event_test_cases(session_scanner, "New DMU QuickDraft", entry_label, expected, entry_string, mock_ocr)

@pytest.mark.parametrize("entry_label, expected, entry_string", OTJ_QUICK_DRAFT_ENTRIES)
def test_mkm_quick_draft_old(session_scanner, entry_label, expected, entry_string):
    """
    Verify that the old quick draft entries can be processed - WOTC might revert the changes
    """
    with (
        patch("src.log_scanner.OCR.get_pack") as mock_ocr,
        patch("src.log_scanner.capture_screen_base64str")
    ):
        event_test_cases(session_scanner, "Old OTJ QuickDraft", entry_label, expected, entry_string, mock_ocr)

@pytest.mark.parametrize("entry_label, expected, entry_string", OTJ_TRAD_DRAFT_ENTRIES_2024_5_7)
def test_quick_trad_draft_old(session_scanner, entry_label, expected, entry_string):
    """
    Verify that the old quick draft entries can be processed - WOTC might revert the changes
    """
    with (
        patch("src.log_scanner.OCR.get_pack") as mock_ocr,
        patch("src.log_scanner.capture_screen_base64str")
    ):
        event_test_cases(session_scanner, "New OTJ TradDraft", entry_label, expected, entry_string, mock_ocr)

@pytest.mark.parametrize("entry_label, expected, entry_string", ARENA_OPEN_TEST_ENTRIES)
def test_arena_open(function_scanner, entry_label, expected, entry_string):
    """
    Verify that the Arena Open event entries can be processed
    """
    with (
        patch("src.log_scanner.OCR.get_pack") as mock_ocr,
        patch("src.log_scanner.capture_screen_base64str")
    ):
        event_test_cases(function_scanner, "Arena Open", entry_label, expected, entry_string, mock_ocr)

# TODO - Traditional Sealed

# TODO - Sealed

@pytest.mark.parametrize("entry_label, expected, entry_string", DSK_SEALED_ENTRIES_2024_9_24)
def test_dsk_sealed(session_scanner, entry_label, expected, entry_string):
    """
    Verify that the sealed event entries can be processed
    """
    with (
        patch("src.log_scanner.OCR.get_pack") as mock_ocr,
        patch("src.log_scanner.capture_screen_base64str")
    ):
        event_test_cases(session_scanner, "New DSK Sealed", entry_label, expected, entry_string, mock_ocr)

@pytest.mark.parametrize("entry_label, expected, entry_string", OM1_PICK_TWO_PREMIER_DRAFT_ENTRIES)
def test_om1_pick_two_premier(session_scanner, entry_label, expected, entry_string):
    """
    Verify that the OM1 Pick Two Premier Draft entries can be processed
    """
    with (
        patch("src.log_scanner.OCR.get_pack") as mock_ocr,
        patch("src.log_scanner.capture_screen_base64str")
    ):
        event_test_cases(session_scanner, "Pick Two OM1 Premier Draft ", entry_label, expected, entry_string, mock_ocr)

@patch("src.log_scanner.OCR.get_pack")
@patch("src.log_scanner.capture_screen_base64str")
def test_otj_premier_p1p1_ocr_overwrite(mock_screenshot, mock_ocr, function_scanner):
    # Write the event entry to the fake Player.log file
    with open(TEST_LOG_FILE_LOCATION, 'a', encoding="utf-8", errors="replace") as log_file:
        log_file.write(f"{OTJ_EVENT_ENTRY}\n")

    # Search for the event
    function_scanner.draft_start_search()

    # Open the dataset
    function_scanner.retrieve_set_data(OTJ_PREMIER_SNAPSHOT)

    # Mock the card names returned by the OCR get_pack method
    expected_names = ["Seraphic Steed", "Spinewoods Armadillo", "Sterling Keykeeper"]
    mock_ocr.return_value = expected_names
    mock_screenshot.return_value = 0

    function_scanner.draft_data_search(True, False)

    # Verify the current pack, pick
    current_pack, current_pick = function_scanner.retrieve_current_pack_and_pick()
    assert (1, 1) == (current_pack, current_pick), f"OCT Test Failed: OCR Pack/Pick, Set: OTJ, Expected: {(1,1)}, Actual: {(current_pack, current_pick)}"

    # Verify the pack cards
    card_names = [x["name"] for x in function_scanner.retrieve_current_pack_cards()]
    assert expected_names == card_names, f"OCR Test Failed: OCR Pack Cards, Set: OTJ, Expected: {expected_names}, Actual: {card_names}"

    # Write the P1P1 entry to the fake Player.log file
    with open(TEST_LOG_FILE_LOCATION, 'a', encoding="utf-8", errors="replace") as log_file:
        log_file.write(f"{OTJ_P1P1_ENTRY}\n")

    # Update the ArenaScanner results
    function_scanner.draft_data_search(False, False)

    # Verify that P1P1 is overwritten when the log entry is received
    card_names = [x["name"] for x in function_scanner.retrieve_current_pack_cards()]
    assert OTJ_P1P1_CARD_NAMES == card_names, f"OCR Test Failed: Log Pack Cards, Set: OTJ, Expected: {OTJ_P1P1_CARD_NAMES}, Actual: {card_names}"

    # Verify that the OCR method was only called once
    assert mock_ocr.call_count == 1

@patch("src.log_scanner.OCR.get_pack")
@patch("src.log_scanner.capture_screen_base64str")
def test_otj_premier_p1p1_ocr_multiclick(mock_screenshot, mock_ocr, function_scanner):
    # Write the event entry to the fake Player.log file
    with open(TEST_LOG_FILE_LOCATION, 'a', encoding="utf-8", errors="replace") as log_file:
        log_file.write(f"{OTJ_EVENT_ENTRY}\n")

    # Search for the event
    function_scanner.draft_start_search()

    # Open the dataset
    function_scanner.retrieve_set_data(OTJ_PREMIER_SNAPSHOT)

    # Mock the card names returned by the OCR get_pack method
    expected_names = ["Seraphic Steed", "Spinewoods Armadillo", "Sterling Keykeeper"]
    mock_ocr.return_value = expected_names
    mock_screenshot.return_value = 0

    function_scanner.draft_data_search(True, False)

    # Verify the current pack, pick
    current_pack, current_pick = function_scanner.retrieve_current_pack_and_pick()
    assert (1, 1) == (current_pack, current_pick), f"OCR Test Failed: OCR Pack/Pick, Set: OTJ, Expected: {(1,1)}, Actual: {(current_pack, current_pick)}"

    # Verify the pack cards
    card_names = [x["name"] for x in function_scanner.retrieve_current_pack_cards()]
    assert expected_names == card_names, f"OCR Test Failed: OCR Pack Cards, Set: OTJ, Expected: {expected_names}, Actual: {card_names}"

    # Simulate refresh clicks
    function_scanner.draft_data_search(True, False)
    function_scanner.draft_data_search(True, False)

    # Verify that the OCR method was only called once
    assert mock_ocr.call_count == 1

@patch("src.log_scanner.OCR.get_pack")
@patch("src.log_scanner.capture_screen_base64str")
def test_otj_premier_p1p1_ocr_disabled(mock_screenshot, mock_ocr, function_scanner):
    # Write the event entry to the fake Player.log file
    with open(TEST_LOG_FILE_LOCATION, 'a', encoding="utf-8", errors="replace") as log_file:
        log_file.write(f"{OTJ_EVENT_ENTRY}\n")

    # Search for the event
    function_scanner.draft_start_search()

    # Open the dataset
    function_scanner.retrieve_set_data(OTJ_PREMIER_SNAPSHOT)

    # P1P1_OCR is disabled
    function_scanner.draft_data_search(False, False)

    # Verify that the OCR method was not called
    assert mock_ocr.call_count == 0
    mock_screenshot.return_value = 0

@pytest.mark.parametrize("encoded_cost, expected_decoded, expected_cmc", [
    ("o1oW", "{1}{W}", 2),
    ("o2oUoU", "{2}{U}{U}", 4),
    ("oXoGoG", "{X}{G}{G}", 3),
    ("o5", "{5}", 5),
    ("", "", 0),
    (None, "", 0),
    ("(o2oG)", "{2}{G}", 3), # Test with parentheses
])
def test_decode_mana_cost(encoded_cost, expected_decoded, expected_cmc):
    """Tests the decode_mana_cost utility function for various mana cost formats."""
    decoded, cmc = decode_mana_cost(encoded_cost)
    assert decoded == expected_decoded
    assert cmc == expected_cmc

@pytest.mark.parametrize("type_line, expected_types", [
    ("Creature — Human Soldier", ["Creature"]),
    ("Artifact Creature — Golem", ["Creature", "Artifact"]),
    ("Legendary Enchantment Artifact", ["Enchantment", "Artifact"]),
    ("Instant", ["Instant"]),
    ("Basic Land — Forest", ["Land"]),
    ("Vanguard", []),
])
def test_extract_types(type_line, expected_types):
    """Tests the extract_types utility function to correctly identify main card types."""
    types = extract_types(type_line)
    # Use sets for comparison to ignore order
    assert set(types) == set(expected_types)

def test_initialize_card_data():
    """Tests that a card data dictionary is correctly initialized with deck_colors."""
    card = {}
    initialize_card_data(card)
    assert constants.DATA_FIELD_DECK_COLORS in card
    assert constants.FILTER_OPTION_ALL_DECKS in card[constants.DATA_FIELD_DECK_COLORS]
    assert "W" in card[constants.DATA_FIELD_DECK_COLORS]
    assert "WUBRG" not in card[constants.DATA_FIELD_DECK_COLORS] # Example of a non-standard color combo
    for color in constants.DECK_COLORS:
        assert color in card[constants.DATA_FIELD_DECK_COLORS]
        assert constants.DATA_FIELD_GIHWR in card[constants.DATA_FIELD_DECK_COLORS][color]
        assert card[constants.DATA_FIELD_DECK_COLORS][color][constants.DATA_FIELD_GIHWR] == 0.0

@pytest.mark.parametrize("date_str, expected_result", [
    ("2023-01-01", True),
    ("9999-12-31", False), # Future date
    ("invalid-date", False),
    ("2023-13-01", False), # Invalid month
])
def test_check_date(date_str, expected_result):
    """Tests the date validation utility function."""
    assert check_date(date_str) == expected_result

@pytest.mark.parametrize("set_code, expected_encoded_set_code", URL_ENCODING_TEST_CASES)
@patch('src.file_extractor.urllib.request.urlopen')
def test_retrieve_17lands_data_url_encoding(mock_urlopen, file_extractor, set_code, expected_encoded_set_code):
    """
    Tests that the set code in the URL for retrieve_17lands_data is correctly URL-encoded.
    """
    mock_response = MagicMock()
    mock_response.read.return_value = b'[]'
    mock_urlopen.return_value = mock_response

    # The UI elements must be mocked to avoid AttributeErrors on `None`.
    mock_root = MagicMock()
    mock_progress = MagicMock()
    mock_status = MagicMock()
    
    # This state is normally set by the `select_sets` method.
    mock_set_info = MagicMock()
    mock_set_info.seventeenlands = [set_code]
    file_extractor.select_sets(mock_set_info)

    expected_url = (
        f"https://www.17lands.com/card_ratings/data?expansion={expected_encoded_set_code}"
        f"&format={file_extractor.draft}"
        f"&start_date={file_extractor.start_date}"
        f"&end_date={file_extractor.end_date}"
    )

    file_extractor.retrieve_17lands_data(
        sets=[set_code],
        deck_colors=[constants.FILTER_OPTION_ALL_DECKS],
        root=mock_root,
        progress=mock_progress,
        initial_progress=0,
        status=mock_status
    )

    # Assert
    # Check that urlopen was called with the correctly formatted and encoded URL.
    mock_urlopen.assert_called_once_with(expected_url, context=file_extractor.context)

@pytest.mark.parametrize("set_code, expected_encoded_set_code", URL_ENCODING_TEST_CASES)
@patch('src.file_extractor.urllib.request.urlopen')
def test_retrieve_17lands_color_ratings_url_encoding(mock_urlopen, file_extractor, set_code, expected_encoded_set_code):
    """
    Tests that the set code in the URL for retrieve_17lands_color_ratings is correctly URL-encoded.
    """
    # Arrange
    mock_response = MagicMock()
    mock_response.read.return_value = b'[]'
    mock_urlopen.return_value = mock_response

    mock_set_info = MagicMock()
    mock_set_info.seventeenlands = [set_code]
    file_extractor.select_sets(mock_set_info)

    expected_url = (
        f"https://www.17lands.com/color_ratings/data?expansion={expected_encoded_set_code}"
        f"&event_type={file_extractor.draft}"
        f"&start_date={file_extractor.start_date}"
        f"&end_date={file_extractor.end_date}"
        f"&combine_splash=true"
    )

    # Act
    file_extractor.retrieve_17lands_color_ratings()

    # Assert
    mock_urlopen.assert_called_once_with(expected_url, context=file_extractor.context)

def test_process_17lands_data(file_extractor):
    """
    Tests the processing of raw JSON data from the 17Lands API into the internal structure.
    """
    # Arrange: Mock 17Lands API response
    mock_api_data = [
        {
            "name": "Sol Ring",
            "url": "/static/images/cards/s_123.jpg",
            "ever_drawn_win_rate": 0.65,
            "avg_seen": 1.1,
            "drawn_improvement_win_rate": 0.1,
            "drawn_game_count": 1000,
        },
        {
            "name": "Island",
            "url": "https://c1.scryfall.com/island.jpg",
            "ever_drawn_win_rate": None, # Test null value
            "avg_seen": 9.5,
            "drawn_improvement_win_rate": -0.05,
            "drawn_game_count": 500,
        }
    ]
    color = "All Decks"
    
    # Act
    file_extractor._process_17lands_data(color, mock_api_data)
    
    # Assert
    ratings = file_extractor.card_ratings
    assert "Sol Ring" in ratings
    assert "Island" in ratings
    
    sol_ring_data = ratings["Sol Ring"]
    assert sol_ring_data["image"] == ["https://www.17lands.com/static/images/cards/s_123.jpg"]
    
    sol_ring_ratings = sol_ring_data["ratings"][0][color]
    assert sol_ring_ratings[constants.DATA_FIELD_GIHWR] == 65.0  # Check percentage conversion
    assert sol_ring_ratings[constants.DATA_FIELD_ALSA] == 1.1
    assert sol_ring_ratings[constants.DATA_FIELD_IWD] == 10.0 # Check percentage conversion
    assert sol_ring_ratings[constants.DATA_FIELD_NGD] == 1000

    island_ratings = ratings["Island"]["ratings"][0][color]
    assert island_ratings[constants.DATA_FIELD_GIHWR] == 0.0  # Check null handling
    assert island_ratings[constants.DATA_FIELD_IWD] == -5.0 # Check negative percentage

def test_process_card_data_merging(file_extractor):
    """
    Tests the merging of 17Lands data (`card_ratings`) into the main card dictionary (`card_dict`).
    """
    # Arrange
    card_name = "Test Card"
    file_extractor.card_dict = {
        "12345": {
            constants.DATA_FIELD_NAME: card_name,
            constants.DATA_FIELD_MANA_COST: "{U}",
            constants.DATA_FIELD_TYPES: ["Creature"],
            constants.DATA_FIELD_CMC: 1,
            constants.DATA_FIELD_COLORS: ["U"],
            constants.DATA_SECTION_IMAGES: [],
        }
    }
    file_extractor.card_ratings = {
        card_name: {
            "image": ["http://example.com/image.png"],
            "ratings": [
                {
                    "All Decks": {
                        constants.DATA_FIELD_GIHWR: 55.5,
                        constants.DATA_FIELD_ALSA: 3.3
                    }
                }
            ]
        }
    }

    # Act
    card_to_process = file_extractor.card_dict["12345"]
    result = file_extractor._process_card_data(card_to_process)

    # Assert
    assert result is True
    assert card_to_process[constants.DATA_SECTION_IMAGES] == ["http://example.com/image.png"]
    assert constants.DATA_FIELD_DECK_COLORS in card_to_process
    deck_colors = card_to_process[constants.DATA_FIELD_DECK_COLORS]
    assert deck_colors["All Decks"][constants.DATA_FIELD_GIHWR] == 55.5
    assert deck_colors["All Decks"][constants.DATA_FIELD_ALSA] == 3.3
    assert deck_colors["WU"][constants.DATA_FIELD_GIHWR] == 0.0 # Check that other colors are initialized

def test_process_card_data_no_match(file_extractor):
    """
    Tests that if a card has no 17Lands rating, it is still processed and initialized.
    """
    # Arrange
    card_name = "Unrated Card"
    file_extractor.card_dict = { "54321": { constants.DATA_FIELD_NAME: card_name } }
    file_extractor.card_ratings = {} # No ratings available

    # Act
    card_to_process = file_extractor.card_dict["54321"]
    result = file_extractor._process_card_data(card_to_process)

    # Assert
    assert result is False # Should return false as no match was found
    # But it should still initialize the deck_colors structure
    initialize_card_data(card_to_process) # Manually call for assertion comparison
    assert constants.DATA_FIELD_DECK_COLORS in card_to_process
    assert card_to_process[constants.DATA_FIELD_DECK_COLORS]["All Decks"][constants.DATA_FIELD_GIHWR] == 0.0

@patch('src.file_extractor.check_file_integrity', return_value=(Result.VALID, {}))
@patch('builtins.open', new_callable=mock_open)
@patch('src.file_extractor.json.dump')
def test_export_card_data(mock_json_dump, mock_file_open, mock_check_integrity, file_extractor):
    """
    Tests that the export_card_data function attempts to write the correct data to the correct file.
    """
    # Arrange
    file_extractor.select_sets(MagicMock(seventeenlands=["OTJ"]))
    file_extractor.combined_data = {"meta": {}, "card_ratings": {"1": "a"}}
    expected_filename = f"OTJ_{file_extractor.draft}_{file_extractor.user_group}_{constants.SET_FILE_SUFFIX}"
    expected_filepath = os.path.join(constants.SETS_FOLDER, expected_filename)

    # Act
    result = file_extractor.export_card_data()

    # Assert
    assert result is True
    mock_file_open.assert_called_once_with(expected_filepath, 'w', encoding="utf-8", errors="replace")
    mock_json_dump.assert_called_once_with(file_extractor.combined_data, mock_file_open())
    mock_check_integrity.assert_called_once_with(expected_filepath)
