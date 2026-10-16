"""Writes boards.json: synthetic boards (valid and invalid) for the validation
and boards tests. Run: python3 make_boards.py"""

import copy
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "..", "events", "corpus")


def read(name):
    with open(os.path.join(CORPUS, name), newline="") as f:
        return f.read()


def sp(type, x=0, y=0, **kw):
    s = {"x": x, "y": y, "z": 0, "type": type}
    s.update(kw)
    return s


def base(game):
    return {
        "name": "Synthetic", "description": "", "game": game, "type": "NORMAL", "difficulty": 3,
        "spaces": [sp(7, 10, 10), sp(1, 20, 10), sp(2, 30, 10), sp(0, 40, 10, star=True),
                   sp(1, 50, 10), sp(0, 60, 10, star=True)],
        "links": {"0": 1, "1": 2, "2": 3, "3": 4, "4": 5, "5": 1},
        "events": {},
        "bg": {"width": 960, "height": 720, "src": ""},
        "otherbg": {},
        "audioType": 0,
        "audioIndex": 0,
    }


boards = {}
for game in (1, 2, 3):
    def add(name, fn):
        b = base(game)
        fn(b)
        boards["mp%d_%s" % (game, name)] = b

    add("valid", lambda b: None)
    add("no_start", lambda b: b["spaces"][0].update(type=1))
    add("dead_end", lambda b: b["links"].pop("5"))
    add("start_dead", lambda b: b["links"].pop("0"))
    add("too_many_paths", lambda b: b["links"].update({"1": [2, 3, 4]}))
    add("blue_split", lambda b: b["links"].update({"1": [2, 4]}))
    add("other_split", lambda b: b["links"].update({"3": [4, 1]}))
    add("character_on_path", lambda b: b["spaces"][2].update(subtype=3))
    add("gate_on_path", lambda b: b["spaces"][3].update(subtype=8))

    def subtypes(b):
        for st, n in ((3, 3), (1, 2), (2, 2), (5, 3), (7, 3), (8, 3), (0, 1)):
            for i in range(n):
                b["spaces"].append(sp(0, 100 + 10 * i, 100 + 10 * st, subtype=st))
    add("many_subtypes", subtypes)

    def one_each(b):
        for st in (3, 1, 2, 5, 7):
            b["spaces"].append(sp(0, 100, 100 + 10 * st, subtype=st))
    add("one_of_each_subtype", one_each)
    add("no_stars", lambda b: [s.pop("star", None) for s in b["spaces"]])
    add("one_star", lambda b: b["spaces"][5].pop("star"))
    add("nine_stars", lambda b: b["spaces"].extend(sp(0, 200 + i, 200, star=True) for i in range(7)))
    add("seven_stars", lambda b: b["spaces"].extend(sp(0, 200 + i, 200, star=True) for i in range(5)))
    add("rotations", lambda b: b["spaces"].extend(sp(13, 300 + i, 300, rotation=i * 10) for i in range(9)))
    add("many_spaces", lambda b: b["spaces"].extend(sp(1, i, 400) for i in range(130)))
    add("few_colors", lambda b: [s.update(type=0) for s in b["spaces"][1:3]])

    def events(b):
        b["spaces"][1]["events"] = [{"id": "NOPE", "activationType": 1, "executionType": 1}]
        b["spaces"][2]["events"] = [{"id": "BOWSER", "activationType": 1, "executionType": 1},
                                    {"id": "BANK", "activationType": 1, "executionType": 1}]
        b["spaces"][4]["events"] = [{"id": "BANK", "activationType": 1, "executionType": 1},
                                    {"id": "BANK", "activationType": 1, "executionType": 1},
                                    {"id": "ITEMSHOP", "activationType": 1, "executionType": 1}]
    add("events", events)

    def custom(b):
        b["events"] = {
            "Main Entry": {"language": 0, "code": read("main_entry.s")},
            "Bad Label": read("bad_label.s"),
            "CRLF Event": {"language": 0, "code": read("crlf.s")},
        }
        b["spaces"][1]["events"] = [{"id": "Main Entry", "activationType": 3, "executionType": 2,
                                     "custom": True}]
        b["spaces"][2]["events"] = [{"id": "Bad Label", "activationType": 3, "executionType": 1,
                                     "custom": True}]
        b["spaces"][4]["events"] = [{"id": "Main Entry", "activationType": 3, "executionType": 2,
                                     "custom": True,
                                     "parameterValues": {"enabled": True, "lower_case_prop": 1}}]
        b["boardevents"] = [{"id": "CRLF Event", "activationType": -2, "executionType": 2,
                             "custom": True, "parameterValues": {"dest": 1}},
                            {"id": "Main Entry", "activationType": -3, "executionType": 2,
                             "custom": True, "parameterValues": {"enabled": False}}]
    add("custom_events", custom)

    def gate_ok(b):
        # start -> 1 -> 6 (other) -> 7 (gate) -> 8 (other) -> 9 (blue) -> 1
        b["spaces"].extend([sp(0, 70, 70), sp(0, 80, 70, subtype=8), sp(0, 90, 70), sp(1, 100, 70)])
        b["links"] = {"0": 1, "1": [2, 6], "2": 3, "3": 4, "4": 5, "5": 1, "6": 7, "7": 8,
                      "8": 9, "9": 1}
    add("gate_ok", gate_ok)

    def gate_variant(name, change):
        def fn(b):
            gate_ok(b)
            change(b)
        add(name, fn)

    gate_variant("gate_not_invisible", lambda b: b["spaces"][7].update(type=1))
    gate_variant("gate_two_exits", lambda b: b["links"].update({"7": [8, 9]}))
    gate_variant("gate_exit_visible", lambda b: b["spaces"][8].update(type=1))
    gate_variant("gate_exit_gate", lambda b: b["spaces"][8].update(subtype=8))
    gate_variant("gate_exit_two_in", lambda b: b["links"].update({"5": [1, 8]}))
    gate_variant("gate_after_two_out", lambda b: b["links"].update({"8": [9, 1]}))
    gate_variant("gate_next_gate", lambda b: b["spaces"][9].update(subtype=8, type=0))
    gate_variant("gate_two_in", lambda b: b["links"].update({"2": [3, 7]}))
    gate_variant("gate_entry_visible", lambda b: b["spaces"][6].update(type=1))
    gate_variant("gate_entry_two_in", lambda b: b["links"].update({"4": [5, 6]}))

    add("no_audio_type", lambda b: b.pop("audioType"))
    add("no_audio_index", lambda b: b.pop("audioIndex"))
    add("custom_audio_missing", lambda b: b.update(audioType=1))
    add("custom_audio_object", lambda b: b.update(audioType=1, audioData={}))
    add("custom_audio_empty", lambda b: b.update(audioType=1, audioData=[]))
    add("bg_code_ok", lambda b: b.update(additionalbg=["x"], additionalbgcode=read("crlf.s").split("main:")[1]))
    add("bg_code_bad", lambda b: b.update(additionalbgcode={"language": 0, "code": "  j missing_label\n  nop"}))
    add("audio_code_bad", lambda b: b.update(audioSelectCode={"language": 0, "code": "  jal nothing_here\n  nop"}))

boards["mp2_on_other"] = copy.deepcopy(boards["mp2_valid"])

with open(os.path.join(HERE, "boards.json"), "w") as f:
    json.dump(boards, f, indent=0, sort_keys=True)
print(len(boards))
