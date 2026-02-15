import coc
import interactions as ipy

def hero_sum_check(target: coc.Player, min_value: int) -> bool:
    hero_sum = sum(hero.level for hero in target.heroes if hero.is_home_base)
    if hero_sum < (min_value):
        return False
    return True


def hero_max_check(target: coc.Player, min_value: int) -> bool:
    hero_sum = sum(hero.level for hero in target.heroes if hero.is_home_base)
    hero_max_sum = sum(hero.get_max_level_for_townhall(target.town_hall) for hero in target.heroes if hero.is_home_base)
    hero_max_percentage = (hero_sum / hero_max_sum) * 100

    if hero_max_percentage < (min_value):
        return False
    return True


def overall_max_check(target: coc.Player, min_value: int) -> bool:
    th = target.town_hall
    hero_sum = sum(hero.level for hero in target.heroes if hero.is_home_base)
    hero_max_sum = sum(hero.get_max_level_for_townhall(th) for hero in target.heroes if hero.is_home_base)
    troop_sum = sum(troop.level for troop in target.troops if troop.is_home_base)
    troop_max_sum = sum(troop.get_max_level_for_townhall(th) for troop in target.troops if troop.is_home_base)
    spell_sum = sum(spell.level for spell in target.spells if spell.is_home_base)
    spell_max_sum = sum(spell.get_max_level_for_townhall(th) for spell in target.spells if spell.is_home_base)
    overall_max_percentage = (hero_sum + troop_sum + spell_sum) / (hero_max_sum + troop_max_sum + spell_max_sum) * 100

    if overall_max_percentage < (min_value):
        return False
    return True

CLAN_CHECKS = {
    "hero_sum": hero_sum_check,
    "hero_max": hero_max_check,
    "overall_max": overall_max_check,
}

CLAN_CHECK_NAMES = {
    "hero_sum": "Hero Level Sum",
    "hero_max": "Hero Max Percentage",
    "overall_max": "Overall Max Percentage",
}

CLAN_CHECK_CHOICES = [ipy.SlashCommandChoice(
    name=value, value=key) for key, value in CLAN_CHECK_NAMES.items()]