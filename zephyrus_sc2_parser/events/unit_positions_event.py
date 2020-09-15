import math
from zephyrus_sc2_parser.events.base_event import BaseEvent


class UnitPositionsEvent(BaseEvent):
    def __init__(self, *args):
        super().__init__(*args)

    def _get_target_object(self):
        event = self.event

        if 'None' in event['m_data'] or 'TargetUnit' not in event['m_data']:
            return None

        unit_game_id = event['m_data']['TargetUnit']['m_tag']

        for obj_id, obj in self.player.objects.items():
            if obj.tag == event['m_data']['TargetUnit']['m_snapshotUnitLink']:
                break

        if unit_game_id in self.player.objects:
            return self.player.objects[unit_game_id]
        return None

    def _get_unit(self, unit_index):
        for p in self.game.players.values():
            for u in p.objects.values():
                # return unit if it hasn't died, or died in the last 240 gameloops
                if (u.status != 'died' or (self.gameloop - u.death_time) <= 240) and u.tag == unit_index:
                    return u, p
        return None, None

    def parse_event(self):
        game = self.game
        event = self.event
        gameloop = self.gameloop
        engagement = {
            1: [],
            2: [],
        }

        army_position = {
            1: None,
            2: None,
        }

        distance_to_command_structure = {
            1: {
                1: None,
                2: None,
            },
            2: {
                1: None,
                2: None,
            },
        }

        command_structures = [
            'Nexus',
            'CommandCenter',
            'OrbitalCommand',
            'PlanetaryFortress',
            'Hatchery',
            'Lair',
            'Hive',
        ]

        engagement_resources = {
            1: {
                'live': 0,
                'died': 0,
            },
            2: {
                'live': 0,
                'died': 0,
            },
        }

        for p in game.players.values():
            if not p.army_positions:
                continue

            for obj in p.objects.values():
                if 'building' not in obj.type and 'died' in obj.status and obj.death_time >= (gameloop - 240):
                    engagement[p.player_id].append(obj)
                    engagement_resources[p.player_id]['died'] += obj.mineral_cost
                    engagement_resources[p.player_id]['died'] += obj.gas_cost

        unit_index = event['m_firstUnitIndex']
        for i in range(0, len(event['m_items']), 3):
            unit_index += event['m_items'][i + 0]
            unit_x = event['m_items'][i + 1] * 4
            unit_y = event['m_items'][i + 2] * 4
            # unit identified by unitIndex at the current event['_gameloop'] time is at approximate position (x, y)

            current_unit, unit_owner = self._get_unit(unit_index)
            if current_unit and unit_owner:
                current_unit.position = {
                    'x': unit_x,
                    'y': unit_y,
                }
                current_unit.prev_positions.append((gameloop, current_unit.position))
                current_unit.target_position = None
                engagement[unit_owner.player_id].append(current_unit)
                engagement_resources[unit_owner.player_id]['live'] += current_unit.mineral_cost
                engagement_resources[unit_owner.player_id]['live'] += current_unit.gas_cost

        for player_id, units in engagement.items():
            min_avg_unit_distance = None
            for unit in units:
                engagement_resources[player_id] += unit.mineral_cost
                engagement_resources[player_id] += unit.gas_cost
                unit_distances = []
                for compare_unit in units:
                    if unit != compare_unit:
                        # calculate distance between units
                        unit_distances.append(unit.calc_distance(compare_unit.position))
                # calculate average distance to current unit position
                if unit_distances:
                    avg_unit_distance = sum(unit_distances) / len(unit_distances)
                    if not min_avg_unit_distance or avg_unit_distance < min_avg_unit_distance[0]:
                        min_avg_unit_distance = (avg_unit_distance, unit)
            if min_avg_unit_distance:
                army_position[player_id] = min_avg_unit_distance[1].position

        for p_id, current_army_position in army_position.items():
            if not current_army_position:
                continue

            for player in game.players.values():
                min_structure_distance = None
                for obj in player.objects.values():
                    if obj.name in command_structures:
                        structure_distance = obj.calc_distance(current_army_position)
                        if not min_structure_distance or structure_distance < min_structure_distance[0]:
                            min_structure_distance = (structure_distance, obj)
                if min_structure_distance:
                    distance_to_command_structure[p_id][player.player_id] = min_structure_distance[0]

        for player_id, structure_distances in distance_to_command_structure.items():
            opp_id = 1 if player_id == 2 else 2
            player_distance = structure_distances[player_id]
            opp_distance = structure_distances[opp_id]

            if not player_distance or not opp_distance:
                continue

            total_distance = player_distance + opp_distance
            # calculate proportion of distance to each base, limiting value to domain of -1 to 1
            # then add 1 to bring domain to 0 to 2, then half to bring domain to 0 to 1
            army_position_proportion = (((player_distance / total_distance) - (opp_distance / total_distance)) + 1) / 2
            game.players[player_id].army_positions.append((army_position_proportion, army_position[player_id], gameloop))
        game.engagements.append({
            1: {
                'units': engagement[1],
                'army_value': engagement_resources[1],
            },
            2: {
                'units': engagement[2],
                'army_value': engagement_resources[2],
            },
        })
