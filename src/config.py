from xml.etree import ElementTree as ET
from dataclasses import dataclass
from typing import Optional

from PyQt6.QtGui import QFontDatabase

from common import Label, get_new_path


@dataclass
class Color:
    r: int
    g: int
    b: int

    @staticmethod
    def unpack(value: int):
        return Color((value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF)

    @staticmethod
    def pack(color: "Color"):
        return ((color.r & 0xFF) << 16) | ((color.g & 0xFF) << 8) | (color.b & 0xFF)


@dataclass
class Pos:
    x: int
    y: int


@dataclass
class Font:
    index: int
    name: str
    path: str

    def __post_init__(self):
        if self.name is None:
            raise ValueError("ERROR: the font's name is none")

        if self.path is None:
            raise ValueError("ERROR: the font's path is none")


@dataclass
class TextSettings:
    index: int
    name: str
    font: int
    size: float
    bold: bool
    color: Color
    color_max: Color

    def __post_init__(self):
        if self.name is None:
            raise ValueError("ERROR: the name is none")


@dataclass
class Counter:
    min: int
    max: int
    increment: int
    text_settings_index: int

    def __post_init__(self):
        self.value = self.min
        self.show = False

    def incr(self):
        if self.show:
            self.value += self.increment

            if self.value > self.max:
                self.show = False
        else:
            self.value = self.min
            self.show = True

    def decr(self):
        if self.show:
            self.value -= self.increment

            if self.value < self.min:
                self.show = False
        else:
            self.value = self.max
            self.show = True


@dataclass
class InventoryItem:
    index: int
    name: str
    paths: list[str]
    counter: Optional[Counter]
    positions: list[Pos]
    enabled: bool
    scale_content: bool
    is_reward: bool
    flag_index: Optional[int]
    use_checkmark: bool


@dataclass
class RewardItem:
    name: str
    text_settings_index: int


@dataclass
class FlagItem:
    texts: list[str]
    pos: Pos
    text_settings_index: int
    hidden: bool


class Rewards:
    def __init__(self):
        self.index = 0
        self.items: list[RewardItem] = []


class Inventory:
    def __init__(self):
        self.index = int()
        self.name = str()
        self.background: Optional[str] = None
        self.song_check_path: Optional[str] = None
        self.items: list[InventoryItem] = []
        self.rewards = Rewards()

        # { item_index: { pos_index: data } }
        self.label_map: dict[int, dict[int, Label]] = {}


@dataclass
class GoModeSettings:
    pos: Pos
    hide_if_disabled: bool
    path: str
    light_path: Optional[str]
    light_pos: Optional[Pos]

    def __post_init__(self):
        if self.path is None:
            raise RuntimeError("ERROR: path unset!")


class Config:
    def __init__(self, config_file: str):
        self.config_file = config_file

        self.default_inv = 0
        self.fonts: list[Font] = []
        self.text_settings: list[TextSettings] = []
        self.flags: list[FlagItem] = []
        self.inventories: dict[int, Inventory] = {}
        self.state_path: Optional[str] = None
        self.gomode_settings: Optional[GoModeSettings] = None

        self.label_gomode: Optional[Label] = None
        self.label_gomode_light: Optional[Label] = None

        if self.config_file.endswith(".xml"):
            self.parse_xml_config()
        else:
            raise ValueError("ERROR: the config file's format isn't supported yet.")

        self.validate()

        # register external fonts
        for font in self.fonts:
            QFontDatabase.addApplicationFont(get_new_path(f"config/oot/{font.path}"))

        # set the active inventory from default value
        self.active_inv = self.inventories[self.default_inv]

    def get_text_settings(self, text_settings_index: int):
        return self.text_settings[text_settings_index]

    def get_font(self, text_settings: TextSettings):
        return self.fonts[text_settings.font]

    def get_color(self, text_settings: TextSettings, is_max: bool = False):
        return text_settings.color_max if is_max else text_settings.color

    def get_bool_from_string(self, value: str):
        if value == "True":
            return True
        elif value == "False":
            return False
        else:
            raise ValueError(f"ERROR: unknown value '{value}'")

    def parse_xml_config(self):
        try:
            root = ET.parse(self.config_file).getroot()
        except:
            raise FileNotFoundError(f"ERROR: File '{self.config_file}' is missing or malformed.")

        config = root.find("Config")
        if config is None:
            raise RuntimeError("ERROR: config settings not found")

        self.default_inv = int(config.get("DefaultInventory", "0"))
        self.state_path = config.get("StatePath")

        for elem in config:
            match elem.tag:
                case "Fonts":
                    for item in elem:
                        self.fonts.append(Font(int(item.get("Index", "0")), item.get("Name"), item.get("Source")))
                case "TextSettings":
                    for item in elem:
                        self.text_settings.append(
                            TextSettings(
                                int(item.get("Index", "0")),
                                item.get("Name"),
                                int(item.get("FontIndex", "0")),
                                float(item.get("Size", "10")),
                                self.get_bool_from_string(item.get("Bold", "False")),
                                Color.unpack(int(item.get("Color", "0x000000"), 0)),
                                Color.unpack(int(item.get("ColorMax", "0x000000"), 0)),
                            )
                        )
                case "Flags":
                    for item in elem:
                        text = item.get("Text")
                        if text is None:
                            raise ValueError(f"ERROR: Missing texts for the flag")
                        text_list = text.split(";")

                        pos = item.get("Pos")
                        if pos is None:
                            raise ValueError(f"ERROR: Missing positions for the flag")
                        pos_list = pos.split(";")
                        if len(pos_list) > 2:
                            raise ValueError(f"ERROR: Found more than 2 positions for the flag")

                        self.flags.append(
                            FlagItem(
                                text_list,
                                Pos(int(pos_list[0]), int(pos_list[1])),
                                int(item.get("TextSettings", "0")),
                                self.get_bool_from_string(item.get("Hidden", "True")),
                            )
                        )
                case "GoMode":
                    position = elem.get("Pos")
                    if position is None:
                        raise RuntimeError("ERROR: go mode position missing")

                    pos = position.split(";")
                    if len(pos) > 2:
                        raise RuntimeError("ERROR: go mode have more than 2 positions (X;Y)")

                    light_position = elem.get("LightPos")
                    light_pos = None
                    if light_position is not None:
                        light_pos = light_position.split(";")
                        if len(light_pos) > 2:
                            raise RuntimeError("ERROR: go mode light have more than 2 positions (X;Y)")

                    self.gomode_settings = GoModeSettings(
                        Pos(int(pos[0]), int(pos[1])),
                        self.get_bool_from_string(elem.get("HideIfDisabled", "False")),
                        elem.get("Source"),
                        elem.get("LightPath"),
                        Pos(int(light_pos[0]), int(light_pos[1])) if light_pos is not None else None,
                    )
                case "Inventory":
                    inventory = Inventory()
                    inventory.index = int(elem.get("Index", "0"))
                    inventory.name = elem.get("Name", "Unknown")
                    inventory.background = elem.get("Background")

                    check_path = elem.get("CheckmarkPath")
                    if check_path is not None:
                        inventory.song_check_path = get_new_path(f"config/oot/{check_path}")

                    for i, item in enumerate(elem.iterfind("Item")):
                        name = item.get("Name", "Unknown")
                        path = item.get("Source")
                        pos = item.get("Pos")
                        paths: list[str] = []
                        positions: list[Pos] = []

                        if path is None:
                            sources = item.find("Sources")
                            for sub_item in sources:
                                paths.append(sub_item.get("Path"))
                        else:
                            paths.append(path)

                        if pos is None:
                            pos_node = item.find("Positions")
                            for sub_item in pos_node:
                                positions.append(Pos(int(sub_item.get("X", "0")), int(sub_item.get("Y", "0"))))
                        else:
                            pos_list = pos.split(";")
                            if len(pos_list) > 2:
                                raise ValueError(f"ERROR: Found more than 2 positions for item '{name}'")
                            positions.append(Pos(int(pos_list[0]), int(pos_list[1])))

                        if None in paths:
                            raise ValueError(f"ERROR: Missing path(s) for item '{name}'")

                        if len(positions) == 0:
                            raise ValueError(f"ERROR: Missing positions for item '{name}'")

                        counter = None
                        c = item.find("Counter")
                        if c is not None:
                            counter = Counter(
                                int(c.get("Min", "0")),
                                int(c.get("Max", "0")),
                                int(c.get("Increment", "0")),
                                int(c.get("TextSettings", "0")),
                            )

                        flag_index = item.get("FlagIndex")
                        inventory.items.append(
                            InventoryItem(
                                i,
                                name,
                                paths,
                                counter,
                                positions,
                                self.get_bool_from_string(item.get("Enabled", "False")),
                                self.get_bool_from_string(item.get("ScaleContent", "False")),
                                self.get_bool_from_string(item.get("Reward", "False")),
                                int(flag_index) if flag_index is not None else None,
                                self.get_bool_from_string(item.get("UseCheckmark", "False")),
                            )
                        )

                    rewards = elem.find("Rewards")
                    if rewards is not None:
                        for i, item in enumerate(rewards.iterfind("Item")):
                            inventory.rewards.items.append(
                                RewardItem(
                                    item.get("Name", "Unk"),
                                    int(item.get("TextSettings", "0")),
                                )
                            )

                    self.inventories[inventory.index] = inventory
                case _:
                    raise RuntimeError(f"ERROR: unknown configuration tag: '{elem.tag}'")

    def validate(self):
        if len(self.fonts) == 0:
            raise RuntimeError("ERROR: you need at least one font")

        if len(self.text_settings) == 0:
            raise RuntimeError("ERROR: you need at least one text setting for counter display")

        for inv in self.inventories.values():
            if len(inv.items) == 0:
                raise RuntimeError(f"ERROR: there's no inventory items for inventory at index {inv.index}")

            if inv.background is None:
                raise RuntimeError(f"ERROR: the background's path is none for inventory at index {inv.index}")
