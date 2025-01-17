from dataclasses import dataclass
from typing import Optional
from pathlib import Path

from PyQt6.QtGui import QPixmap

from config import Config
from common import show_error, GLOBAL_HALF_OPACITY


WARNING_TEXT = "!" * 63 + "\n!!! WARNING: DO NOT EDIT UNLESS YOU KNOW WHAT YOU ARE DOING !!!\n" + "!" * 63 + "\n\n"


@dataclass
class LabelState:
    index: int
    pos_index: int
    name: str
    img_index: int
    counter_value: int
    counter_show: bool
    enabled: bool
    reward_index: int
    flag_index: Optional[int]
    flag_text_index: int
    show_flag: bool
    show_extra_img: bool


class State:
    def __init__(self, config: Config, path: Optional[Path] = None):
        self.config = config
        self.states: list[LabelState] = []
        self.gomode_visibility = False
        self.gomode_light_visibility = False

        if path is not None:
            self.path = path
        else:
            self.path = self.config.state_path

        if not self.path.suffix == ".txt":
            self.path = self.path / ".txt"

    def get_states_from_labels(self):
        gomodefx = self.config.label_gomode.label_effect

        if gomodefx is not None:
            self.gomode_visibility = gomodefx.strength() == 0.0

        if self.config.label_gomode_light is not None:
            self.gomode_light_visibility = self.config.label_gomode_light.isVisible()
        else:
            self.gomode_light_visibility = False

        for index, sub_map in self.config.active_inv.label_map.items():
            for i, label in sub_map.items():
                item = self.config.active_inv.items[index]
                self.states.append(
                    LabelState(
                        index,
                        i,
                        item.name,
                        label.img_index,
                        (item.counter.value if item.counter is not None else 0),
                        (item.counter.show if item.counter is not None else False),
                        label.label_effect.strength() == 0.0 if label.label_effect is not None else False,
                        label.reward_index,
                        item.flag_index,
                        label.flag_text_index,
                        label.label_flag.isVisible() if label.label_flag is not None else False,
                        label.label_extra_img.isVisible() if label.label_extra_img is not None else False,
                    )
                )

    def get_states_from_file(self, filedata: str):
        new_state = None
        found_global_settings = False

        for i, line in enumerate(filedata):
            line = line.strip()

            if line == "" or i == 0:
                if found_global_settings:
                    found_global_settings = False
                else:
                    if new_state is not None:
                        self.states.append(new_state)
                    new_state = LabelState(0, 0, "", 0, 0, False, False, 0, None, 0, False, False)

                    if line == "":
                        continue

            if not found_global_settings and line.startswith("Global Settings"):
                found_global_settings = True
            else:
                if line.startswith("gomode_visibility"):
                    self.gomode_visibility = True if line.split(" = ")[1] == "True" else False
                elif line.startswith("gomode_light_visibility"):
                    self.gomode_light_visibility = True if line.split(" = ")[1] == "True" else False
                elif new_state is not None:
                    if line.startswith("Label #"):
                        new_state.index = int(line.split("#")[1].removesuffix(":"))
                    elif line != "":
                        value = line.split(" = ")[1]

                        if line.startswith("pos_index"):
                            new_state.pos_index = int(value)
                        elif line.startswith("name"):
                            new_state.name = value.removeprefix("'").removesuffix("'")
                        elif line.startswith("enabled"):
                            new_state.enabled = True if value == "True" else False
                        elif line.startswith("img_index"):
                            new_state.img_index = int(value)
                        elif line.startswith("counter_value"):
                            new_state.counter_value = int(value)
                        elif line.startswith("counter_show"):
                            new_state.counter_show = True if value == "True" else False
                        elif line.startswith("reward_index"):
                            new_state.reward_index = int(value)
                        elif line.startswith("flag_index"):
                            new_state.flag_index = int(value) if value != "None" else None
                        elif line.startswith("flag_text_index"):
                            new_state.flag_text_index = int(value)
                        elif line.startswith("show_flag"):
                            new_state.show_flag = True if value == "True" else False
                        elif line.startswith("show_extra_img"):
                            new_state.show_extra_img = True if value == "True" else False

    def open(self):
        if self.path is None:
            show_error("ERROR: import path not set")

        with self.path.open("r") as file:
            filedata = file.read().removeprefix(WARNING_TEXT).split("\n")

        self.get_states_from_file(filedata)

        self.config.label_gomode.update_gomode(self.gomode_visibility)

        if self.config.label_gomode_light is not None:
            self.config.label_gomode_light.setVisible(self.gomode_light_visibility)

        for state in self.states:
            item = self.config.active_inv.items[state.index]
            label = None

            for i, _ in enumerate(item.positions):
                if i == state.pos_index:
                    label = self.config.active_inv.label_map[state.index][i]
                    break
                else:
                    label = None

            if label is not None:
                if label.name != state.name:
                    print(f"WARNING: name mismatch! ignoring the current label... ('{label.name}', '{state.name}')")
                    continue

                if item.counter is not None:
                    item.counter.value = state.counter_value
                    item.counter.show = state.counter_show

                    if item.counter.value % item.counter.increment:
                        print("WARNING: the counter's value doesn't match how it's incremented")

                    if item.counter.show:
                        label.label_counter.setText(f"{item.counter.value}")
                        label.label_counter.set_text_style(
                            item.counter.text_settings_index, item.counter.value == item.counter.max
                        )

                if state.img_index < 0:
                    path_index = 0
                else:
                    path_index = state.img_index

                label.img_index = state.img_index
                label.original_pixmap = QPixmap(str(item.paths[path_index]))
                label.setPixmap(label.original_pixmap)
                if not state.enabled:
                    label.set_pixmap_opacity(GLOBAL_HALF_OPACITY)

                if item.is_reward:
                    label.reward_index = state.reward_index
                    for i, _ in enumerate(item.positions):
                        if label.objectName().endswith(f"_pos_{i}"):
                            reward = item.reward_map[i]

                            if reward is not None and reward.item_label is not None:
                                item.update_reward(i, self.config.active_inv.rewards.items[label.reward_index])

                if label.label_effect is not None:
                    label.label_effect.setStrength(0.0 if state.enabled else 1.0)

                item.flag_index = state.flag_index
                label.flag_text_index = state.flag_text_index

                if item.flag_index is not None and label.label_flag is not None:
                    flag = self.config.flags[item.flag_index]
                    total = len(flag.texts) - 1
                    is_max = False if item.is_reward else label.flag_text_index == total

                    label.label_flag.setText(flag.texts[label.flag_text_index])
                    label.label_flag.set_text_style(flag.text_settings_index, is_max)
                    label.label_flag.setVisible(state.show_flag)

                if label.label_extra_img is not None:
                    label.label_extra_img.setVisible(state.show_extra_img)

        self.config.state_saved = True

    def save(self):
        if self.path is None:
            show_error("ERROR: export path not set")

        self.get_states_from_labels()

        with self.path.open("w") as file:
            file.write(
                WARNING_TEXT
                + (
                    "Global Settings:\n\t"
                    + f"gomode_visibility = {self.gomode_visibility}\n\t"
                    + f"gomode_light_visibility = {self.gomode_light_visibility}\n\n"
                )
                + "\n".join(
                    f"Label #{s.index:02}:\n\t"
                    + f"pos_index = {s.pos_index}\n\t"
                    + f"name = '{s.name}'\n\t"
                    + f"enabled = {s.enabled}\n\t"
                    + f"img_index = {s.img_index}\n\t"
                    + f"counter_value = {s.counter_value}\n\t"
                    + f"counter_show = {s.counter_show}\n\t"
                    + f"reward_index = {s.reward_index}\n\t"
                    + f"flag_index = {s.flag_index}\n\t"
                    + f"flag_text_index = {s.flag_text_index}\n\t"
                    + f"show_flag = {s.show_flag}\n\t"
                    + f"show_extra_img = {s.show_extra_img}\n"
                    for s in self.states
                )
            )

        self.config.state_saved = True
