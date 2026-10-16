"""Built-in events shared by the games, dispatching to each game's version (events.common.ts)."""

from ...types import EditorEventActivationType, EventExecutionType, EventParameterType, Game
from ..event_library import add_event_to_library
from ..events import Event

from . import chain_merge_event  # noqa: F401  (registers CHAINMERGE)

from .mp1.u.star_event1 import StarEvent1
from .mp1.u.boo_event1 import BooEvent1
from .mp3.u.gate_close_event3 import GateClose3
from .mp3.u.gate_event3 import Gate3
from .mp2.u.boo_event2 import BooEvent2
from .mp3.u.boo_event3 import BooEvent3
from .mp2.u.star_event2 import StarEvent2
from .mp3.u.star_event3 import StarEvent3
from .mp2.u.bank_event2 import BankEvent2
from .mp3.u.bank_event3 import BankEvent3
from .mp2.u.item_shop_event2 import ItemShopEvent2
from .mp3.u.item_shop_event3 import ItemShopEvent3


def _boo_parse(data_view, info):
    v = info["game_version"]
    if v == 1:
        return BooEvent1.parse(data_view, info)
    if v == 2:
        return BooEvent2.parse(data_view, info)
    if v == 3:
        return BooEvent3.parse(data_view, info)
    return None


def _boo_write(data_view, event, info, temp):
    v = info["game_version"]
    if v == 1:
        return BooEvent1.write(data_view, event, info, temp)
    if v == 2:
        return BooEvent2.write(data_view, event, info, temp)
    if v == 3:
        return BooEvent3.write(data_view, event, info, temp)
    return None


BooEvent = Event(
    id="BOO",
    name="Visit Boo",
    activation_type=EditorEventActivationType.WALKOVER,
    execution_type=EventExecutionType.DIRECT,
    supported_games=[Game.MP1_USA, Game.MP2_USA, Game.MP3_USA],
    parse=_boo_parse,
    write=_boo_write,
)
add_event_to_library(BooEvent)


def _star_parse(data_view, info):
    v = info["game_version"]
    if v == 1:
        return StarEvent1.parse(data_view, info)
    if v == 2:
        return StarEvent2.parse(data_view, info)
    return False


def _star_write(data_view, event, info, temp):
    v = info["game_version"]
    if v == 1:
        return StarEvent1.write(data_view, event, info, temp)
    if v == 2:
        return StarEvent2.write(data_view, event, info, temp)
    if v == 3:
        return StarEvent3.write(data_view, event, info, temp)
    return False


StarEvent = Event(
    id="STAR",
    name="Buy star",
    activation_type=EditorEventActivationType.WALKOVER,
    execution_type=EventExecutionType.DIRECT,
    fake_event=True,
    supported_games=[Game.MP1_USA, Game.MP2_USA, Game.MP3_USA],
    parse=_star_parse,
    write=_star_write,
)
add_event_to_library(StarEvent)


def _bank_parse(data_view, info):
    v = info["game_version"]
    if v == 1:
        return False
    if v == 2:
        return BankEvent2.parse(data_view, info)
    if v == 3:
        return BankEvent3.parse(data_view, info)
    return False


def _bank_write(data_view, event, info, temp):
    v = info["game_version"]
    if v == 1:
        return False
    if v == 2:
        return BankEvent2.write(data_view, event, info, temp)
    if v == 3:
        return BankEvent3.write(data_view, event, info, temp)
    return False


BankEvent = Event(
    id="BANK",
    name="Visit Bank",
    activation_type=EditorEventActivationType.WALKOVER,
    execution_type=EventExecutionType.DIRECT,
    supported_games=[Game.MP2_USA, Game.MP3_USA],
    parse=_bank_parse,
    write=_bank_write,
)
add_event_to_library(BankEvent)


def _item_shop_parse(data_view, info):
    v = info["game_version"]
    if v == 1:
        return False
    if v == 2:
        return ItemShopEvent2.parse(data_view, info)
    if v == 3:
        return ItemShopEvent3.parse(data_view, info)
    return False


def _item_shop_write(data_view, event, info, temp):
    v = info["game_version"]
    if v == 1:
        return False
    if v == 2:
        return ItemShopEvent2.write(data_view, event, info, temp)
    if v == 3:
        return ItemShopEvent3.write(data_view, event, info, temp)
    return False


ItemShopEvent = Event(
    id="ITEMSHOP",
    name="Visit Item Shop",
    activation_type=EditorEventActivationType.WALKOVER,
    execution_type=EventExecutionType.DIRECT,
    supported_games=[Game.MP2_USA, Game.MP3_USA],
    parse=_item_shop_parse,
    write=_item_shop_write,
)
add_event_to_library(ItemShopEvent)


def _gate_parse(data_view, info):
    v = info["game_version"]
    if v == 3:
        return Gate3.parse(data_view, info)
    return False


def _gate_write(data_view, event, info, temp):
    v = info["game_version"]
    if v == 3:
        return Gate3.write(data_view, event, info, temp)
    return False


Gate = Event(
    id="GATE",
    name="Skeleton Key Gate",
    activation_type=EditorEventActivationType.WALKOVER,
    execution_type=EventExecutionType.PROCESS,
    fake_event=True,
    supported_games=[
        # Game.MP2_USA,
        Game.MP3_USA,
    ],
    parse=_gate_parse,
    write=_gate_write,
)
add_event_to_library(Gate)


def _gate_close_parse(data_view, info):
    v = info["game_version"]
    if v == 3:
        return GateClose3.parse(data_view, info)
    return False


def _gate_close_write(data_view, event, info, temp):
    v = info["game_version"]
    if v == 3:
        return GateClose3.write(data_view, event, info, temp)
    return False


# Event that actually occurs on the gate space itself to cause it to close.
GateClose = Event(
    id="GATECLOSE",
    name="Skeleton Key Gate Close",
    activation_type=EditorEventActivationType.WALKOVER,
    execution_type=EventExecutionType.DIRECT,
    parameters=[{"name": "gateIndex", "type": EventParameterType.Number.value}],
    fake_event=True,
    supported_games=[
        # Game.MP2_USA,
        Game.MP3_USA,
    ],
    parse=_gate_close_parse,
    write=_gate_close_write,
)
add_event_to_library(GateClose)
