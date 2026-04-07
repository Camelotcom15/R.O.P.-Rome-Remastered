__author__ = "jorellaf"

from pathlib import Path as p
import re
import json

DATADIR = (
    p(__file__).parent.absolute() / "data"
).resolve()

PRINT_INTERVAL = 500

traits = []
trait_triggers = []
vnvs_strings = []
missing_vnvs_strings = []

ancillaries = []
ancillary_triggers = []
ancillary_strings = []
missing_ancillary_strings = []

settlements = []
missing_settlements = []
docudemon_conditions = []
factions = []

traits_affected = []

original_file = ""

logfile = (p(__file__).parent.absolute() / "traits_log.txt").resolve()
open(logfile, "w").close()

traits_logfile = logfile

ancillaries_logfile = (p(__file__).parent.absolute() / "ancillaries_log.txt").resolve()
open(ancillaries_logfile, "w").close()


def read_file(path: p, text_file: bool = False):
    file = ""

    encoding = "utf-8" if not text_file else "utf-16"

    with open(path, encoding=encoding) as f:
        file = f.read()

    original_file = file

    if not text_file:
        file = re.sub("^;.*\n", "", file, flags=re.MULTILINE)
        file = re.sub(";.*", "", file, flags=re.MULTILINE)
    else:
        file = re.sub("^¬.*\n", "", file, flags=re.MULTILINE)
        file = re.sub("¬.*", "", file, flags=re.MULTILINE)

    return file, original_file


def parse_comma_list(definition_string: str, string_to_parse: str, object_start: int):
    pattern_object = rf"^\s*{definition_string}\s+(\w+,* *\t*)+"

    objects = (
        re.search(pattern_object, string_to_parse, flags=re.MULTILINE)
        if re.search(pattern_object, string_to_parse, flags=re.MULTILINE)
        else None
    )

    object_start = objects.start() if objects is not None else object_start

    object_list = []

    if objects:
        objects = re.split(rf"^\s*{definition_string}\s+", objects.group())[1]
        object_list = re.findall(r"(\w+),*\s*", objects)

    object_list = object_list if len(object_list) > 0 else None

    return object_start, object_list


def calculate_line(file: str, string_to_find: str, offset: int = 0):
    idx = file.index(string_to_find)
    return str(file[:idx].count("\n") + 1 + offset)


num_errors = 0
num_warnings = 0


def print_to_log(line: int, error_string: str, warning: bool = False):
    with open(logfile, mode="a") as log:
        print(
            f"{'ERROR' if not warning else 'WARNING'} at line {line}: {error_string}",
            file=log,
        )
    global num_errors, num_warnings
    num_errors += 1 if not warning else 0
    num_warnings += 1 if warning else 0


def parse_levels(trait: str, trait_name: str, original_file: str):
    start_level = 0
    pattern_level = re.compile(r"^[\t ]*+Level\s+([^\s]+).*", flags=re.MULTILINE)
    pattern_level_end = re.compile(
        r"^((Trait)|(Trigger)|((\t| )+Level))\s+([^\s]+).*", flags=re.MULTILINE
    )

    levels_list = []
    level_id = 1

    while (level_def := pattern_level.search(trait, start_level)) is not None:
        level_start = level_def.start()
        level_end = (
            pattern_level_end.search(trait, level_def.end()).start() - 1
            if pattern_level_end.search(trait, level_def.end())
            else len(trait)
        )

        level = trait[level_start:level_end]

        level_name = level_def.groups()[0]

        level_description = re.search(
            r"^\s+Description\s+([^\s]+)", level, flags=re.MULTILINE
        ).groups()[0]

        level_effects_description = re.search(
            r"^\s+EffectsDescription\s+([^\s]+)([\t ]*)*",
            level,
            flags=re.MULTILINE,
        ).groups()[0]

        level_gain_message = re.search(
            r"^\s+GainMessage\s+([^\s]+)([\t ]*)*", level, flags=re.MULTILINE
        )
        level_gain_message = (
            level_gain_message.groups()[0] if level_gain_message is not None else None
        )

        level_lose_message = re.search(
            r"^\s+LoseMessage\s+([^\s]+)([\t ]*)*", level, flags=re.MULTILINE
        )
        level_lose_message = (
            level_lose_message.groups()[0] if level_lose_message is not None else None
        )

        level_epithet = re.search(
            r"^\s+Epithet\s+([^\s]+)([\t ]*)*", level, flags=re.MULTILINE
        )
        level_epithet = level_epithet.groups()[0] if level_epithet is not None else None

        def missing_strings_error_handler(string: str, original_file: str):
            if (
                string not in [x["String_Id"] for x in vnvs_strings]
                and string not in missing_vnvs_strings
            ):
                print_to_log(
                    calculate_line(
                        original_file,
                        level.split("\n")[0],
                        level[: level.index(string)].count("\n"),
                    ),
                    f"Missing string in export_VnVs for string '{string}' for trait {trait_name}",
                )
                missing_vnvs_strings.append(string)

        missing_strings_error_handler(level_name, original_file)
        missing_strings_error_handler(level_description, original_file)
        missing_strings_error_handler(level_effects_description, original_file)
        if level_gain_message:
            missing_strings_error_handler(level_gain_message, original_file)
        if level_lose_message:
            missing_strings_error_handler(level_lose_message, original_file)
        if level_epithet:
            missing_strings_error_handler(level_epithet, original_file)

        level_threshold = re.search(
            r"^\s+Threshold\s+(\d+)", trait, flags=re.MULTILINE
        ).groups()[0]

        level_effects = re.findall(r"\s+Effect\s+(\w+)\s+(-?\d+)", level)

        level_effects = [
            {"Effect": x[0], "EffectAmount": int(x[1])} for x in level_effects
        ]

        levels_list.append(
            {
                "Level": level_id,
                "LevelName": level_name,
                "Description": level_description,
                "EffectsDescription": level_effects_description,
                "GainMessage": level_gain_message,
                "LoseMessage": level_lose_message,
                "Epithet": level_epithet,
                "Threshold": int(level_threshold),
                "Effects": level_effects,
            }
        )

        level_id += 1
        start_level = level_def.end()

    return levels_list


def parse_traits():
    file, original_file = read_file(DATADIR / "export_descr_character_traits.txt")

    pattern = re.compile(r"^Trait\s+([^\s]+).*", flags=re.MULTILINE)

    pattern_end = re.compile(r"^((Trait)|(Trigger))\s+(\w+).*", flags=re.MULTILINE)

    start = 0
    num_traits = 0

    while (trait_def := pattern.search(file, start)) is not None:
        trait_start = trait_def.start()
        trait_end = (
            pattern_end.search(file, trait_def.end()).start() - 1
            if pattern_end.search(file, trait_def.end())
            else len(file)
        )

        trait = file[trait_start:trait_end]

        trait_start_line = calculate_line(original_file, trait.split("\n")[0])

        trait_name = trait_def.groups()[0]

        current_char = 0
        trait_character = re.search(
            r"^\s*Characters\s+(\w+)", trait, flags=re.MULTILINE
        )
        current_char = trait_character.start()
        trait_character = trait_character.groups()[0]

        hidden = re.search(r"^\s*Hidden\s+", trait, flags=re.MULTILINE)
        prev_char = current_char
        current_char = hidden.start() if hidden is not None else current_char
        hidden = (
            True
            if re.search(r"^\s*Hidden\s+", trait, flags=re.MULTILINE) is not None
            else False
        )
        if prev_char > current_char:
            print_to_log(
                calculate_line(
                    original_file,
                    trait.split("\n")[0],
                    trait[:current_char].count("\n") + 1,
                ),
                "Hidden line must go after Characters line",
            )

        prev_char = current_char
        current_char, exclude_cultures_list = parse_comma_list(
            "ExcludeCultures", trait, current_char
        )
        if prev_char > current_char:
            print_to_log(
                calculate_line(
                    original_file,
                    trait.split("\n")[0],
                    trait[:current_char].count("\n") + 1,
                ),
                "ExcludeCultures line must go after Characters and Hidden* lines",
            )

        no_going_back_level = re.search(
            r"^\s+NoGoingBackLevel\s+(\d+)", trait, flags=re.MULTILINE
        )
        if no_going_back_level is not None:
            prev_char = current_char
            current_char = no_going_back_level.start()
            no_going_back_level = no_going_back_level.groups()[0]
            if prev_char > current_char:
                print_to_log(
                    calculate_line(
                        original_file,
                        trait.split("\n")[0],
                        trait[:current_char].count("\n") + 1,
                    ),
                    "NoGoingBackLevel line must go after Characters, Hidden*, and ExcludeCultures* lines",
                )

        prev_char = current_char
        current_char, anti_traits_list = parse_comma_list(
            "AntiTraits", trait, current_char
        )
        if prev_char > current_char:
            print_to_log(
                calculate_line(
                    original_file,
                    trait.split("\n")[0],
                    trait[:current_char].count("\n") + 1,
                ),
                "AntiTraits line must go after Characters, Hidden*, ExcludeCultures*, and NoGoingBackLevel* lines",
            )

        levels_list = parse_levels(trait, trait_name, original_file)

        traits.append(
            {
                "TraitName": trait_name,
                "Characters": trait_character,
                "Hidden": hidden,
                "ExcludeCultures": exclude_cultures_list,
                "NoGoingBackLevel": no_going_back_level,
                "AntiTraits": anti_traits_list,
                "Levels": levels_list,
                "StartLine": trait_start_line,
            }
        )

        start = trait_def.end()
        num_traits += 1

    seen = set()
    duplicates = [
        x
        for x in [
            {"TraitName": x["TraitName"], "StartLine": x["StartLine"]}
            for x in traits
            if x["TraitName"] in seen or seen.add(x["TraitName"])
        ]
    ]
    if len(duplicates) > 0:
        for duplicate in duplicates:
            print_to_log(
                duplicate["StartLine"],
                f"Trait name {duplicate['TraitName']} is a duplicate",
                True,
            )

    global num_errors
    global num_warnings
    print(
        f"Parsed and validated all {num_traits} traits and found {num_errors} errors and {num_warnings} warnings"
    )
    num_errors = 0
    num_warnings = 0


def parse_condition_line(
    condition_line: str,
    trigger_name: str,
    trigger: str,
    original_file: str,
    condition_found: bool = False,
    is_first_condition: bool = False,
):
    condition_pattern = r"^[\t ]*(and|or)?[\t ]*(not)?[\t ]*([\w!\-]+)[\t ]*([\w!\-]+)?[\t ]*([^\s\w]+)*[\t ]*([^\s]+)*"
    condition_toggle_pattern = r"^[\t ]*(and|or)?[\t ]*(not)?[\t ]*(Toggled)\s+(.+)"

    condition_is_toggled = False

    condition_parsed = {}

    condition_list = re.search(
        condition_pattern,
        condition_line,
        flags=re.MULTILINE,
    )
    condition_list = (
        re.search(condition_toggle_pattern, condition_line, flags=re.MULTILINE)
        if condition_list is None or condition_list.groups()[2] == "Toggled"
        else condition_list
    )
    condition_list = (
        condition_list
        if (
            condition_list.groups()[0] not in ("and", "or", "and not", "or not")
            and is_first_condition
        )
        or (
            condition_list.groups()[0] in ("and", "or", "and not", "or not")
            and not is_first_condition
        )
        else None
    )

    condition_line_num = (
        calculate_line(
            original_file,
            trigger.split("\n")[0],
            trigger[: trigger.index(condition_line)].count("\n"),
        ),
    )[0]

    if condition_list is not None:
        condition_found = True
        condition_is_toggled = (
            True if condition_list.groups()[2] == "Toggled" else False
        )

        if not condition_found:
            print_to_log(
                condition_line_num,
                f"Condition is coded incorrectly for trigger '{trigger_name}'",
            )
        else:
            condition_name = condition_list.groups()[2]
            item = condition_list.groups()[3]
            op = None
            val = None

            if condition_is_toggled:
                condition_parsed = {
                    "conj": condition_list.groups()[0]
                    if condition_list.groups()[0] != ""
                    else None,
                    "neg": True if condition_list.groups()[1] == "not" else False,
                    "cond": condition_list.groups()[2],
                    "item": None,
                    "op": None,
                    "val": condition_list.groups()[3],
                }
                item = None
                val = condition_list.groups()[3]
            else:
                condition_parsed = {
                    "conj": condition_list.groups()[0]
                    if condition_list.groups()[0] != ""
                    else None,
                    "neg": True if condition_list.groups()[1] == "not" else False,
                    "comp": condition_list.groups()[2],
                    "item": condition_list.groups()[3]
                    if condition_list.groups()[3] != ""
                    else None,
                    "op": condition_list.groups()[4]
                    if condition_list.groups()[4] != ""
                    else None,
                    "val": condition_list.groups()[5]
                    if condition_list.groups()[5] != ""
                    else None,
                }
                op = condition_list.groups()[4]
                val = condition_list.groups()[5]

            global docudemon_conditions

            docudemon_definition = []

            if condition_name not in [x[0] for x in docudemon_conditions]:
                print_to_log(
                    condition_line_num,
                    f"Condition {condition_name} not recognised for Trigger '{trigger_name}'",
                )
            else:
                docudemon_definition = [
                    {
                        "Identifier": x[0],
                        "Parameters": x[1],
                        "Implemented": True if x[2] else False,
                    }
                    for x in docudemon_conditions
                    if x[0] == condition_name
                ][0]

                if (
                    item is None
                    and op is None
                    and val is None
                    and docudemon_definition["Parameters"][0] != "None"
                    and docudemon_definition["Parameters"][0].strip() != ""
                ):
                    print_to_log(
                        condition_line_num,
                        f"Condition {condition_name} is missing parameters! At Trigger '{trigger_name}'",
                    )
                elif (item is not None or op is not None or val is not None) and (
                    docudemon_definition["Parameters"][0] == "None"
                    or docudemon_definition["Parameters"][0].strip() == ""
                ):
                    print_to_log(
                        condition_line_num,
                        f"Condition {condition_name} cannot receive any parameters! At Trigger '{trigger_name}'",
                    )
                elif len(docudemon_definition["Parameters"]) > 3:
                    print_to_log(
                        condition_line_num,
                        f"Validator cannot yet validate {condition_name} since it has more than 3 parameters. At Trigger '{trigger_name}'",
                        True,
                    )
                elif op is None and (
                    "logic token" in docudemon_definition["Parameters"]
                    or "logic_token" in docudemon_definition["Parameters"]
                ):
                    print_to_log(
                        condition_line_num,
                        f"Condition {condition_name} missing logic operator! At Trigger '{trigger_name}'",
                    )
                elif (
                    op is not None
                    and op not in ("=", ">=", "<=", ">", "<")
                    and not condition_is_toggled
                ):
                    print_to_log(
                        condition_line_num,
                        f"Condition {condition_name} has invalid logic operator '{op}'! At Trigger '{trigger_name}'",
                    )
                elif docudemon_definition["Identifier"].find("Trait") >= 0:
                    if item not in [x["TraitName"] for x in traits]:
                        print_to_log(
                            condition_line_num,
                            f"Condition {condition_name} is trying to compare a non-existent trait '{item}'. At Trigger '{trigger_name}'",
                        )
                elif docudemon_definition["Identifier"].find("Ancillary") >= 0:
                    if item not in [x["AncillaryName"] for x in ancillaries]:
                        print_to_log(
                            condition_line_num,
                            f"Condition {condition_name} is trying to compare a non-existent ancillary '{item}'. At Trigger '{trigger_name}'",
                        )
                elif val is None and (
                    "logic token" in docudemon_definition["Parameters"]
                    or "logic_token" in docudemon_definition["Parameters"]
                ):
                    print_to_log(
                        condition_line_num,
                        f"Condition {condition_name} missing value to compare! At Trigger '{trigger_name}'",
                    )
                elif docudemon_definition["Identifier"] in (
                    "SettlementName",
                    "I_SettlementExists",
                    "I_SettlementOwner",
                    "I_SettlementOwnerCulture",
                    "I_SettlementLevel",
                    "I_SettlementSelected",
                    "I_AmountOfUnitInSettlement",
                ):
                    if item not in [x["Settlement"] for x in settlements]:
                        print_to_log(
                            condition_line_num,
                            f"Condition {condition_name} uses settlement {item} not in database! At Trigger '{trigger_name}'",
                            True,
                        )
                elif (
                    re.search(r"faction.?type", docudemon_definition["Parameters"][0])
                    and item not in factions
                ):
                    print_to_log(
                        condition_line_num,
                        f"Condition {condition_name} uses faction {item} not in database! At Trigger '{trigger_name}'",
                        True,
                    )
                elif len(docudemon_definition["Parameters"]) > 1:
                    if (
                        re.search(
                            r"faction.?type",
                            docudemon_definition["Parameters"][1]
                            or re.search(
                                r"faction.?type", docudemon_definition["Parameters"][2]
                            ),
                        )
                    ) and val not in factions:
                        print_to_log(
                            condition_line_num,
                            f"Condition {condition_name} uses faction {val} not in database! At Trigger '{trigger_name}'",
                            True,
                        )

    else:
        print_to_log(
            condition_line_num,
            f"Condition code cannot be parsed for trigger '{trigger_name}'",
        )

    return condition_parsed, condition_found


def parse_conditions(
    conditions: str, trigger_name: str, trigger: str, original_file: str
):
    first_condition_found = False
    first_condition_in_group = (
        True if re.match(r"[\t ]*\w*[\t ]*\(", conditions) else False
    )

    condition_groups = re.findall(
        r"([A-Za-z_]+[\t ]*\w*)?[\t ]*(\(\s+[^)]*\))", conditions, flags=re.DOTALL
    )
    condition_groups = condition_groups if len(condition_groups) > 0 else None
    top_level_conditions = conditions

    condition_group_lines = []

    if condition_groups:
        if first_condition_in_group:
            if condition_groups[0][0] == "":
                first_condition_found = True
            else:
                print_to_log(
                    calculate_line(
                        original_file,
                        trigger.split("\n")[0],
                        trigger[: trigger.index(condition_groups[0][1])].count("\n"),
                    ),
                    f"There should NOT be a logical operator before the 1st condition group for trigger '{trigger_name}' when it is the first condition",
                )
        elif condition_groups[0][0] == "":
            print_to_log(
                calculate_line(
                    original_file,
                    trigger.split("\n")[0],
                    trigger[: trigger.index(condition_groups[0][1])].count("\n"),
                ),
                f"There should be a logical operator before the 1st condition group for trigger '{trigger_name}'",
            )

        for idx, condition_group in enumerate(condition_groups):
            if condition_group[0] == "" and idx > 0:
                print_to_log(
                    calculate_line(
                        original_file,
                        trigger.split("\n")[0],
                        trigger[: trigger.index(condition_group[1])].count("\n"),
                    ),
                    f"There should be a logical operator before the {idx + 1}{'nd' if idx == 1 else 'rd' if idx == 2 else 'th'} condition group for trigger '{trigger_name}'",
                )
            condition_group_operator = condition_group[0].strip()

            condition_group_lines = (
                condition_group[1].replace("(", "").replace(")", "").strip().split("\n")
            )
            condition_group_lines = [x.strip() for x in condition_group_lines]

            for idy, condition_group_line in enumerate(condition_group_lines):
                condition_group_lines[idy], _ = parse_condition_line(
                    condition_group_line,
                    trigger_name,
                    trigger,
                    original_file,
                    is_first_condition=(True if idy == 0 else False),
                )

            if not first_condition_in_group and idx == 0:
                condition_group_lines.insert(0, condition_group_operator)
                if not (condition_group_lines[0] in ("and", "or", "and not", "or not")):
                    print_to_log(
                        calculate_line(
                            original_file,
                            trigger.split("\n")[0],
                            trigger[: trigger.index(condition_group[1])].count("\n"),
                        ),
                        f"There should be a logical operator before the {idx + 1}{'nd' if idx == 1 else 'rd' if idx == 2 else 'th'} condition group for trigger '{trigger_name}'",
                    )

            condition_groups[idx] = condition_group_lines

            top_level_conditions = top_level_conditions.replace(
                condition_group[0] + condition_group[1], str(idx)
            )

    top_level_conditions = [
        x for x in top_level_conditions.split("\n") if x.strip() != ""
    ]
    top_level_conditions = [x.strip() for x in top_level_conditions]

    conditions_obj = []

    if not first_condition_in_group:
        first_condition, first_condition_found = parse_condition_line(
            top_level_conditions[0],
            trigger_name,
            trigger,
            original_file,
            is_first_condition=True,
        )
        if first_condition_found:
            conditions_obj.append(first_condition)
    elif first_condition_found:
        conditions_obj.append(condition_groups[0])

    for condition in top_level_conditions[1:]:
        if condition.isdigit():
            conditions_obj.append(condition_groups[int(condition)])
        else:
            condition_line, _ = parse_condition_line(
                condition, trigger_name, trigger, original_file
            )
            conditions_obj.append(condition_line)

    return conditions_obj


def parse_triggers(ancillary: bool = False):
    file, original_file = (
        read_file(DATADIR / "export_descr_character_traits.txt")
        if not ancillary
        else read_file(DATADIR / "export_descr_ancillaries.txt")
    )

    pattern = re.compile(r"^Trigger\s+([^\s]+).*", flags=re.MULTILINE)

    pattern_end = (
        re.compile(r"^((Trait)|(Trigger))\s+(\w+).*", flags=re.MULTILINE)
        if not ancillary
        else re.compile(r"^((Ancillary)|(Trigger))\s+(\w+).*", flags=re.MULTILINE)
    )

    start = 0
    num_triggers = 0

    while (trigger_def := pattern.search(file, start)) is not None:
        trigger_start = trigger_def.start()
        trigger_end = (
            pattern_end.search(file, trigger_def.end()).start() - 1
            if pattern_end.search(file, trigger_def.end())
            else len(file)
        )

        trigger = file[trigger_start:trigger_end]

        trigger_start_line = calculate_line(original_file, trigger.split("\n")[0])

        trigger_name = trigger_def.groups()[0]

        when_to_test = re.search(
            r"^\s*WhenToTest\s+(\w+)", trigger, flags=re.MULTILINE
        ).groups()[0]

        affects = re.findall(
            r"^[\t ]*Affects\s+(\w+)\s+(Lose)?\s*(-?\d+)\s+Chance\s+(\d+)",
            trigger,
            flags=re.MULTILINE,
        )

        conditions = None
        condition_start = re.search(r"^\s*Condition\s+", trigger, flags=re.MULTILINE)
        if condition_start is not None:
            condition_start = condition_start.end()
            condition_end = re.search(
                r"\n+^[\t ]*(Affects)|(AcquireAncillary)|(RemoveAncillary)\s+.*",
                trigger,
                flags=re.MULTILINE,
            ).start()
            conditions = trigger[condition_start:condition_end]

            conditions = parse_conditions(
                conditions, trigger_name, trigger, original_file
            )

        affects_list = [
            {"AffectsTrait": x[0], "AffectsAmount": int(x[2]), "Chance": int(x[3])}
            if x[1] != "Lose"
            else {
                "AffectsTrait": x[0],
                "AffectsAmount": -int(x[2]),
                "Chance": int(x[3]),
            }
            for x in affects
        ]

        if len(affects_list) > 10:
            print_to_log(
                calculate_line(original_file, trigger.split("\n")[0]),
                f"Triggers cannot affect more than 10 traits at once. Found for trigger '{trigger_name}'",
            )

        for affects in affects_list:
            if affects["AffectsTrait"] not in [x["TraitName"] for x in traits]:
                print_to_log(
                    calculate_line(
                        original_file,
                        trigger.split("\n")[0],
                        trigger[
                            : re.search(
                                rf"Affects {affects['AffectsTrait']}", trigger
                            ).start()
                        ].count("\n"),
                    ),
                    f"Trigger '{trigger_name}' affects non-existent trait '{affects['AffectsTrait']}'",
                )
            else:
                traits_affected.append(affects["AffectsTrait"])

        if not ancillary:
            trait_triggers.append(
                {
                    "Trigger": trigger_name,
                    "WhenToTest": when_to_test,
                    "Conditions": conditions,
                    "Affects": affects_list,
                    "StartLine": trigger_start_line,
                }
            )
        else:
            acquire_ancillary = re.search(
                r"^[\t ]*AcquireAncillary\s+([^\s]+)\s+chance\s+(\d+)",
                trigger,
                flags=re.MULTILINE,
            )
            acquire_ancillary = (
                {
                    "AcquireAncillary": acquire_ancillary.groups()[0],
                    "chance": acquire_ancillary.groups()[1],
                }
                if acquire_ancillary
                else None
            )

            remove_ancillary = re.search(
                r"^[\t ]*RemoveAncillary\s+([^\s]+)\s+chance\s+(\d+)",
                trigger,
                flags=re.MULTILINE,
            )
            remove_ancillary = (
                {
                    "RemoveAncillary": remove_ancillary.groups()[0],
                    "chance": remove_ancillary.groups()[1],
                }
                if remove_ancillary
                else None
            )

            if (
                acquire_ancillary is None
                and affects is None
                and remove_ancillary is None
            ):
                print_to_log(
                    calculate_line(
                        original_file,
                        trigger.split("\n")[0],
                        0,
                    ),
                    f"Trigger '{trigger_name}' must have at least one Affects or AcquireAncillary/RemoveAncillary line",
                )

            ancillary_triggers.append(
                {
                    "Trigger": trigger_name,
                    "WhenToTest": when_to_test,
                    "Conditions": conditions,
                    "Affects": affects_list,
                    "AcquireAncillary": acquire_ancillary,
                    "RemoveAncillary": remove_ancillary,
                    "StartLine": trigger_start_line,
                }
            )

        start = trigger_def.end()
        num_triggers += 1

    seen = set()
    duplicates = [
        x
        for x in [
            {"Trigger": x["Trigger"], "StartLine": x["StartLine"]}
            for x in trait_triggers
            if x["Trigger"] in seen or seen.add(x["Trigger"])
        ]
    ]
    if len(duplicates) > 0:
        for duplicate in duplicates:
            print_to_log(
                duplicate["StartLine"],
                f"Trigger name {duplicate['Trigger']} is a duplicate! This will cause CTDs",
            )

    global num_errors
    global num_warnings
    print(
        f"Parsed and validated all {num_triggers}{' ancillary' if ancillary else ''} triggers and found {num_errors} errors and {num_warnings} warnings"
    )
    num_errors = 0
    num_warnings = 0


def parse_ancillaries():
    file, original_file = read_file(DATADIR / "export_descr_ancillaries.txt")

    pattern = re.compile(r"^Ancillary\s+([^\s]+).*", flags=re.MULTILINE)

    pattern_end = re.compile(r"^((Ancillary)|(Trigger))\s+(\w+).*", flags=re.MULTILINE)

    start = 0
    num_ancillaries = 0

    while (ancillary_def := pattern.search(file, start)) is not None:
        ancillary_start = ancillary_def.start()
        ancillary_end = (
            pattern_end.search(file, ancillary_def.end()).start() - 1
            if pattern_end.search(file, ancillary_def.end())
            else len(file)
        )

        ancillary = file[ancillary_start:ancillary_end]

        ancillary_start_line = calculate_line(original_file, ancillary.split("\n")[0])

        ancillary_name = ancillary_def.groups()[0]

        ancillary_image = re.search(
            r"^\s+Image\s+([^\s]+)", ancillary, flags=re.MULTILINE
        ).groups()[0]

        current_char = 0

        unique = re.search(r"^\s*Unique\s+", ancillary, flags=re.MULTILINE)
        current_char = unique.start() if unique is not None else current_char
        unique = (
            True
            if re.search(r"^\s*Unique\s+", ancillary, flags=re.MULTILINE) is not None
            else False
        )

        current_char, exclude_cultures_list = parse_comma_list(
            "ExcludeCultures", ancillary, current_char
        )

        current_char, excluded_ancillaries_list = parse_comma_list(
            "ExcludedAncillaries", ancillary, current_char
        )

        if unique and (
            (
                excluded_ancillaries_list
                and ancillary_name not in excluded_ancillaries_list
            )
            or (excluded_ancillaries_list is None)
        ):
            print_to_log(
                calculate_line(
                    original_file,
                    ancillary.split("\n")[0],
                    ancillary[:current_char].count("\n") + 1,
                ),
                f"If ancillary '{ancillary_name}' is unique, its own name must be included in its own ExcludedAncillaries line",
            )

        if excluded_ancillaries_list is not None and len(excluded_ancillaries_list) > 3:
            print_to_log(
                calculate_line(
                    original_file,
                    ancillary.split("\n")[0],
                    ancillary[:current_char].count("\n") + 1,
                ),
                f"There cannot be more than 3 ancillaries in the ExcludedAncillaries line",
            )

        ancillary_description = re.search(
            r"^\s+Description\s+([^\s]+)", ancillary, flags=re.MULTILINE
        ).groups()[0]

        ancillary_effects_description = re.search(
            r"^\s+EffectsDescription\s+([^\s]+)([\t ]*)*",
            ancillary,
            flags=re.MULTILINE,
        ).groups()[0]

        ancillary_effects = re.findall(r"\s+Effect\s+(\w+)\s+(-?\d+)", ancillary)

        ancillary_effects = [
            {"Effect": x[0], "EffectAmount": int(x[1])} for x in ancillary_effects
        ]

        def missing_strings_error_handler(string: str, original_file: str):
            if (
                string not in [x["String_Id"] for x in ancillary_strings]
                and string not in missing_ancillary_strings
            ):
                print_to_log(
                    calculate_line(
                        original_file,
                        ancillary.split("\n")[0],
                        ancillary[: ancillary.index(string)].count("\n"),
                    ),
                    f"Missing string in export_ancillaries for string '{string}' for ancillary {ancillary_name}",
                )
                missing_ancillary_strings.append(string)

        missing_strings_error_handler(ancillary_description, original_file)
        missing_strings_error_handler(ancillary_effects_description, original_file)

        ancillaries.append(
            {
                "AncillaryName": ancillary_name,
                "Image": ancillary_image,
                "Unique": unique,
                "ExcludedAncillaries": excluded_ancillaries_list,
                "ExcludeCultures": exclude_cultures_list,
                "Description": ancillary_description,
                "EffectsDescription": ancillary_effects_description,
                "Effects": ancillary_effects,
                "StartLine": ancillary_start_line,
            }
        )

        start = ancillary_def.end()
        num_ancillaries += 1

    seen = set()
    duplicates = [
        x
        for x in [
            {"AncillaryName": x["AncillaryName"], "StartLine": x["StartLine"]}
            for x in ancillaries
            if x["AncillaryName"] in seen or seen.add(x["AncillaryName"])
        ]
    ]
    if len(duplicates) > 0:
        for duplicate in duplicates:
            print_to_log(
                duplicate["StartLine"],
                f"Ancillary name {duplicate['AncillaryName']} is a duplicate",
            )

    global num_errors
    global num_warnings
    print(
        f"Parsed and validated all {num_ancillaries} ancillaries and found {num_errors} errors and {num_warnings} warnings"
    )
    num_errors = 0
    num_warnings = 0


def parse_export_texts(ancillary: bool = False):
    file, _ = (
        read_file(DATADIR / "text" / "export_vnvs.txt", True)
        if not ancillary
        else read_file(DATADIR / "text" / "export_ancillaries.txt", True)
    )

    file = re.sub("^¬.*\n", "", file, flags=re.MULTILINE)
    file = re.sub("¬.*", "", file, flags=re.MULTILINE)

    pattern = re.compile(r"{([^}]+)}[\t ]*\n?([^{]+)")

    start = 0

    while (string_def := pattern.search(file, start)) is not None:
        string_end = (
            pattern.search(file, string_def.end()).start() - 1
            if pattern.search(file, string_def.end())
            else len(file)
        )

        string = {
            "String_Id": string_def.groups()[0],
            "String": string_def.groups()[1].strip(),
        }

        if ancillary:
            ancillary_strings.append(string)
        else:
            vnvs_strings.append(string)

        start = string_end


def parse_descr_regions():
    file, _ = read_file(DATADIR / "world/maps/base/descr_regions.txt")

    file = re.sub("^;.*\n", "", file, flags=re.MULTILINE)
    file = re.sub(";.*", "", file, flags=re.MULTILINE)

    pattern = re.compile(r"^([\w-]+)\s+[\t ]+([\w-]+)", flags=re.MULTILINE)

    start = 0

    while (region_def := pattern.search(file, start)) is not None:
        string_end = (
            pattern.search(file, region_def.end()).start() - 1
            if pattern.search(file, region_def.end())
            else len(file)
        )

        region_and_settlement = {
            "Region": region_def.groups()[0],
            "Settlement": region_def.groups()[1].strip(),
        }

        settlements.append(region_and_settlement)

        start = string_end


def parse_docudemon_conditions():
    file, _ = read_file(p(__file__).parent.absolute() / "docudemon_conditions.txt")

    global docudemon_conditions
    docudemon_conditions = re.findall(
        r"Identifier:[\t ]+([^\n]+)\n[^\n]+\nParameters:[\t ]+([^\n]+)\n[^\n]+\n[^\n]+\n[^\n]+\n[^\n]+\nImplemented:[\t ]+([^\n]+)",
        file,
    )

    docudemon_conditions = [
        (x[0], re.split(r",[\t ]+", x[1]), x[2]) for x in docudemon_conditions
    ]

    docudemon_conditions = [
        (x[0], re.sub(r"[\s ]*\([^)]+\)", "", str.join(",", x[1])).split(","), x[2])
        for x in docudemon_conditions
    ]


def parse_sm_factions():
    file, _ = read_file(DATADIR / "descr_sm_factions.txt")

    file = re.sub("^;.*\n", "", file, flags=re.MULTILINE)
    file = re.sub(";.*", "", file, flags=re.MULTILINE)

    file = re.sub(r'"factions"[\t ]*:\s+\[', "{", file, 1)
    file = re.sub(r"(.*)],", r"\1}", file, 1, flags=re.DOTALL)

    file = re.sub(r",\s*[^{\[](}|])", r"\1", file, flags=re.MULTILINE)

    factions_json = json.loads(file)

    global factions
    factions = set(factions_json.keys())


parse_export_texts()
parse_export_texts(True)
parse_descr_regions()
parse_sm_factions()
parse_docudemon_conditions()

parse_traits()

logfile = ancillaries_logfile
parse_ancillaries()
parse_triggers(True)

logfile = traits_logfile
parse_triggers()


affected_set = set(traits_affected)

for trait in traits:
    if trait["TraitName"] not in affected_set:
        print_to_log(
            trait["StartLine"],
            f"Trait {trait['TraitName']} does not have any corresponding triggers",
            True,
        )

with open(p(__file__).parent.absolute() / "json_dump.json", "w") as f:
    json.dump(
        {
            "traits": traits,
            "trait_triggers": trait_triggers,
            "ancillaries": ancillaries,
            "ancillary_triggers": ancillary_triggers,
        },
        f,
        indent=4,
    )
