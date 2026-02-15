"""
Applicant Validation & Eligibility Checks.

This module defines the specific logic used to determine if a Clash of Clans player
meets the requirements for joining specific clans within the alliance.

It provides functions to calculate:
1.  **Hero Level Sum:** The total combined levels of all heroes.
2.  **Hero Max Percentage:** How close the heroes are to being maxed for the player's Town Hall.
3.  **Overall Max Percentage:** A comprehensive metric combining Heroes, Troops, and Spells
    to gauge the overall progression of the account (preventing "rushed" bases).

These functions are mapped in `CLAN_CHECKS` for dynamic execution based on `clans_config.json`.

Dependencies:
    - coc (Clash of Clans API objects)
    - interactions (Discord slash command choices)
"""

import coc
import interactions as ipy

def hero_sum_check(target: coc.Player, min_value: int) -> bool:
    """
    Validates if the player's combined hero levels meet a minimum threshold.

    Args:
        target (coc.Player): The player object fetched from the API.
        min_value (int): The minimum required sum of hero levels.

    Returns:
        bool: True if the sum is greater than or equal to min_value, False otherwise.
    """
    # Sum levels only for Home Base heroes (ignoring Builder Base machine)
    hero_sum = sum(hero.level for hero in target.heroes if hero.is_home_base)
    
    if hero_sum < (min_value):
        return False
    return True


def hero_max_check(target: coc.Player, min_value: int) -> bool:
    """
    Validates if the player's heroes are sufficiently leveled relative to their Town Hall max.
    
    This prevents players with high Town Hall levels but low-level heroes from
    bypassing raw level checks.

    Args:
        target (coc.Player): The player object.
        min_value (int): The minimum percentage (0-100) of max hero levels required.

    Returns:
        bool: True if the player's hero progression meets the percentage.
    """
    # Calculate current hero sum
    hero_sum = sum(hero.level for hero in target.heroes if hero.is_home_base)
    
    # Calculate the theoretical max hero sum for this specific Town Hall level
    # 'get_max_level_for_townhall' handles the game data logic
    hero_max_sum = sum(hero.get_max_level_for_townhall(target.town_hall) for hero in target.heroes if hero.is_home_base)
    
    # Avoid division by zero (though practically impossible for valid TH levels with heroes)
    if hero_max_sum == 0:
        return True

    hero_max_percentage = (hero_sum / hero_max_sum) * 100

    if hero_max_percentage < (min_value):
        return False
    return True


def overall_max_check(target: coc.Player, min_value: int) -> bool:
    """
    Validates the overall account progression (Heroes + Troops + Spells).
    
    This is the most strict check, ensuring the player is not "rushed" across
    any major category (Offense/Heroes).

    Args:
        target (coc.Player): The player object.
        min_value (int): The minimum total completion percentage required.

    Returns:
        bool: True if the overall progression meets the requirement.
    """
    th = target.town_hall
    
    # 1. Hero Calculation
    hero_sum = sum(hero.level for hero in target.heroes if hero.is_home_base)
    hero_max_sum = sum(hero.get_max_level_for_townhall(th) for hero in target.heroes if hero.is_home_base)
    
    # 2. Troop Calculation
    troop_sum = sum(troop.level for troop in target.troops if troop.is_home_base)
    troop_max_sum = sum(troop.get_max_level_for_townhall(th) for troop in target.troops if troop.is_home_base)
    
    # 3. Spell Calculation
    spell_sum = sum(spell.level for spell in target.spells if spell.is_home_base)
    spell_max_sum = sum(spell.get_max_level_for_townhall(th) for spell in target.spells if spell.is_home_base)
    
    # Combine all metrics for a weighted average of account completion
    total_current = hero_sum + troop_sum + spell_sum
    total_max = hero_max_sum + troop_max_sum + spell_max_sum
    
    if total_max == 0:
        return True

    overall_max_percentage = (total_current / total_max) * 100

    if overall_max_percentage < (min_value):
        return False
    return True

# Registry of available check functions.
# Used by the Clan Application system to dynamically call checks defined in JSON config.
CLAN_CHECKS = {
    "hero_sum": hero_sum_check,
    "hero_max": hero_max_check,
    "overall_max": overall_max_check,
}

# User-friendly names for the checks, used in UI/Embeds.
CLAN_CHECK_NAMES = {
    "hero_sum": "Hero Level Sum",
    "hero_max": "Hero Max Percentage",
    "overall_max": "Overall Max Percentage",
}

# Slash Command choices generation for admin commands.
CLAN_CHECK_CHOICES = [
    ipy.SlashCommandChoice(name=value, value=key) 
    for key, value in CLAN_CHECK_NAMES.items()
]