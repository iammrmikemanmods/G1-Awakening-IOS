#include "g1/GameSession.hpp"

#include <algorithm>

namespace g1 {
namespace {
std::int8_t signed_byte(std::uint8_t value) noexcept {
    return static_cast<std::int8_t>(value < 128U ? int(value) : int(value) - 256);
}
std::int32_t increment32(std::int32_t value) noexcept {
    const auto next=static_cast<std::uint32_t>(value)+1U;
    return next<=0x7fffffffU ? static_cast<std::int32_t>(next) :
        static_cast<std::int32_t>(static_cast<std::int64_t>(next)-0x100000000LL);
}
} // namespace

GameSession::GameSession(WorldBootstrap world, std::uint32_t random_seed, CampaignContext campaign)
    : world_(std::move(world)), campaign_(std::move(campaign)), mission_(world_,campaign_),
      captures_(initial_capture_network(world_.sites)), random_(random_seed) {
    // Original cold mission-start57b80..57b9a zeroes income and funds. The
    // network helper's recomputation baseline is not an initial payment.
    captures_.counters_68 = {{0,0}};
    turn_.controllers=campaign_.player_controllers;
    for (const auto& unit : world_.units) {
        MovementUnitState state;
        state.active = unit.active;
        state.form = unit.form;
        state.tile_x = state.anchor_x = unit.x;
        state.tile_y = state.anchor_y = unit.y;
        state.spent_budget = unit.spent_movement;
        units_.push_back(state);
        auto combat=make_combat_unit(unit,world_.unit_definitions.at(unit.type));
        if (unit.spawn.health!=100) set_combat_health(combat,unit.spawn.health);
        combat.damage_immune=unit.spawn.damage_immune;
        combat_.push_back(combat);
        animation_pending_.push_back(0);
    }
    for (const auto& effect:world_.initialization_effects) {
        if (effect.owner>1) throw FormatError("bootstrap economy request has an invalid owner");
        if (effect.kind==WorldInitializationEffectKind::begin_current_player_turn) {
            auto initial_network=initial_capture_network(effect.sites_at_turn_start);
            initial_network.counters_68=captures_.counters_68;
            turn_.current_player=effect.owner;
            begin_current_player_turn(initial_network,
                {{signed_byte(world_.player_factions[0]),signed_byte(world_.player_factions[1])}},turn_);
            captures_.counters_68=initial_network.counters_68;
        } else {
            turn_.funds[effect.owner]=apply_spawn_funds_debit(turn_.funds[effect.owner],effect.signed_cost);
            active_counts_[effect.owner]=static_cast<std::uint8_t>(
                active_counts_[effect.owner]+effect.active_count_increment);
        }
    }
}

CampaignContext GameSession::campaign_context() const {
    auto result=campaign_;
    result.active_unit_counts=active_counts_;
    result.type_12_active=false;
    result.player_factions=world_.player_factions;
    result.player_controllers=turn_.controllers;
    for (std::size_t i=0;i<units_.size();++i) {
        const auto& unit=world_.units[i];
        if (units_[i].active) {
            if (unit.type==12) result.type_12_active=true;
        }
    }
    return result;
}

std::vector<MissionObjectiveUnit> GameSession::objective_units() const {
    std::vector<MissionObjectiveUnit> result(23);
    for (auto& unit:result) unit.present=false;
    for (std::size_t i=0;i<units_.size();++i) {
        const auto& unit=world_.units[i];
        const auto& motion=units_[i];
        result.at(unit.type)={true,motion.active,unit.owner,motion.tile_x,motion.tile_y,
                              motion.offset_x,motion.offset_y};
    }
    return result;
}

bool GameSession::select(std::size_t index) {
    if (moving_ || battle_ || mission_.state().interaction_mode != 0U || index >= units_.size() ||
        !units_[index].active || world_.units[index].owner != turn_.current_player ||
        turn_.controllers[turn_.current_player] == 1)
        return false;
    selected_ = index;
    return true;
}

void GameSession::clear_selection() noexcept {
    if (!moving_) selected_.reset();
}

std::optional<MovementRange> GameSession::selected_movement_range() const {
    if (!selected_ || moving_ || battle_ || mission_.state().interaction_mode != 0U) return std::nullopt;
    const auto index = *selected_;
    const auto& state = units_.at(index);
    const auto& unit = world_.units.at(index);
    if (!state.active || unit.owner != turn_.current_player || state.flag_2c || state.spent_budget ||
        turn_.controllers[turn_.current_player] == 1)
        return std::nullopt;
    return compute_movement_range(world_.movement_board(),world_.movement_profile(index),
                                  state.tile_x,state.tile_y);
}

MoveRequestResult GameSession::move_selected_to(WorldCoordinate destination) {
    if (mission_.state().interaction_mode != 0U || battle_) return MoveRequestResult::script_controls_input;
    if (turn_.controllers[turn_.current_player] == 1) return MoveRequestResult::computer_controls_input;
    if (moving_) return MoveRequestResult::movement_in_progress;
    if (!selected_) return MoveRequestResult::no_selected_unit;
    const auto index = *selected_;
    const auto& state = units_.at(index);
    const auto& unit = world_.units.at(index);
    if (!state.active) return MoveRequestResult::inactive_unit;
    if (unit.owner != turn_.current_player) return MoveRequestResult::other_player;
    if (state.flag_2c) return MoveRequestResult::action_used;
    if (state.spent_budget) return MoveRequestResult::already_moved;
    if (destination.x >= world_.grid.width || destination.y >= world_.grid.height)
        return MoveRequestResult::outside_map;
    for (const auto& other : world_.units)
        if (other.active && other.x == destination.x && other.y == destination.y)
            return MoveRequestResult::occupied_destination;
    const auto profile = world_.movement_profile(index);
    const auto range = compute_movement_range(world_.movement_board(),profile,state.tile_x,state.tile_y);
    if (!range.has_unoccupied_destination || range.at(destination.x,destination.y) < 0 ||
        range.at(destination.x,destination.y) == movement_reserved_cell)
        return MoveRequestResult::no_route;
    auto route = choose_movement_route(range,{state.tile_x,state.tile_y},{destination.x,destination.y});
    if (route.status != MovementRouteStatus::ready || route.steps.empty()) return MoveRequestResult::no_route;
    const auto& definition = world_.unit_definitions.at(unit.type);
    auto action = std::make_unique<MovementAction>(state,profile,range,std::move(route),
                                                  signed_byte(definition.forms.at(0).at(2)));
    action_ = std::move(action);
    moving_ = index;
    units_[index] = action_->state();
    synchronize_unit(index);
    return MoveRequestResult::started;
}

void GameSession::synchronize_unit(std::size_t index) {
    const auto& state = units_.at(index);
    auto& unit = world_.units.at(index);
    unit.active = state.active;
    unit.form = state.form;
    unit.x = state.tile_x;
    unit.y = state.tile_y;
    unit.spent_movement = state.spent_budget;
    auto& combat = combat_.at(index);
    combat.active = state.active;
    combat.form = state.form;
    combat.x = state.tile_x;
    combat.y = state.tile_y;
    combat.flag_38 = state.flag_38;
    combat.timer_30_ms = state.timer_ms;
}

bool GameSession::selected_can_capture() const {
    if (!selected_ || moving_ || battle_ || mission_.state().interaction_mode != 0U ||
        mission_.state().stop != MissionStop::none) return false;
    const auto index = *selected_;
    const auto& state = units_.at(index);
    const auto& unit = world_.units.at(index);
    if (!state.active || state.flag_2c || unit.owner != turn_.current_player ||
        turn_.controllers[turn_.current_player] == 1) return false;
    const auto available = capture_availability(world_.sites,captures_,
        {state.tile_x,state.tile_y},unit.owner);
    return available.item || available.site;
}

CaptureResult GameSession::capture_selected() {
    if (!selected_can_capture()) return {};
    const auto index = *selected_;
    auto& state = units_.at(index);
    const auto& unit = world_.units.at(index);
    const auto& form = world_.unit_definitions.at(unit.type).forms.at(state.form);
    CaptureActor actor{unit.owner,{state.tile_x,state.tile_y},state.active,state.flag_2c,
                       signed_byte(form.at(10))};
    const auto result = perform_capture(world_.sites,captures_,actor,
        {{signed_byte(world_.player_factions[0]),signed_byte(world_.player_factions[1])}},
        turn_.controllers);
    if (result.status == CaptureStatus::captured) {
        state.flag_2c = actor.flag_2c;
        synchronize_unit(index);
        if (result.clear_selection_flags) clear_selection();
    }
    return result;
}

TransformEligibility GameSession::selected_transform_eligibility() const {
    if (!selected_ || moving_ || battle_ || mission_.state().interaction_mode != 0U ||
        mission_.state().stop != MissionStop::none) return TransformEligibility::inactive;
    const auto index=*selected_;
    const auto& state=units_.at(index);
    const auto& unit=world_.units.at(index);
    if (unit.owner != turn_.current_player || turn_.controllers[turn_.current_player] == 1)
        return TransformEligibility::inactive;
    const auto tile=world_.grid.tile_at(state.tile_x,state.tile_y);
    const auto& fields=world_.terrain_rules.at(world_.effective_lookup.at(tile)).fields;
    return transform_eligibility(state,world_.unit_definitions.at(unit.type),
                                  signed_byte(fields[0]),signed_byte(fields[2]));
}

std::optional<TransformResult> GameSession::transform_selected() {
    if (selected_transform_eligibility() != TransformEligibility::allowed) return std::nullopt;
    const auto index=*selected_;
    auto result=transform_unit(units_.at(index),world_.unit_definitions.at(world_.units.at(index).type),
                               combat_.at(index).level,animation_pending_.at(index),true,true);
    units_[index]=result.unit;
    animation_pending_[index]=result.animation_pending_2e;
    combat_[index].stats=result.stats;
    synchronize_unit(index);
    return result;
}

bool GameSession::end_turn_available() const {
    if (moving_ || battle_ || mission_.state().interaction_mode != 0U ||
        mission_.state().stop != MissionStop::none || turn_.controllers[turn_.current_player] == 1)
        return false;
    // The original input loop observes the goal after the capture action.
    // An external UI callback must not switch the player in that short gap.
    if (mission_.state().mission_objective) {
        const auto context=campaign_context();
        const auto by_type=objective_units();
        if (evaluate_mission_objective(*mission_.state().mission_objective,
            {context,by_type,captures_.sites,world_.commands,mission_.state().command_index,
             turn_.current_player}).resume_script) return false;
    }
    return true;
}

CombatRulesView GameSession::combat_rules() const {
    return {world_.grid,world_.effective_lookup,world_.terrain_rules,
            world_.unit_definitions,world_.flag_227};
}

MissionRecord GameSession::mission_record() const noexcept {
    return {turn_.human_turn_counter_274,death_counter_278_,death_counter_27c_};
}

std::vector<std::size_t> GameSession::selected_attack_targets() const {
    std::vector<std::size_t> result;
    if (!selected_ || moving_ || battle_ || mission_.state().interaction_mode!=0 ||
        mission_.state().stop!=MissionStop::none || turn_.controllers[turn_.current_player]==1)
        return result;
    const auto actor=*selected_;
    if (!units_[actor].active || units_[actor].flag_2c ||
        world_.units[actor].owner!=turn_.current_player) return result;
    for (std::size_t i=0;i<combat_.size();++i)
        if (i!=actor && combat_can_target(combat_rules(),combat_,actor,i)) result.push_back(i);
    return result;
}

void GameSession::begin_battle(std::size_t attacker,std::size_t defender) {
    if (battle_ || moving_ || !units_.at(attacker).active || units_[attacker].flag_2c ||
        world_.units.at(attacker).owner!=turn_.current_player ||
        !combat_can_target(combat_rules(),combat_,attacker,defender))
        throw FormatError("native battle action is not authorized by current world state");
    SessionBattle presentation;
    presentation.token=next_battle_token_;
    presentation.attacker=attacker;presentation.defender=defender;
    presentation.attacker_before=combat_.at(attacker);
    presentation.defender_before=combat_.at(defender);
    presentation.exchange=resolve_combat_exchange(combat_rules(),combat_,attacker,defender,random_);
    units_[attacker].flag_2c=1; // Original action path430f4 after585c4.
    for (const auto& dead:presentation.exchange.destroyed) {
        death_log_.push_back({dead.type,dead.x,dead.y,0}); // Original49e26.
        active_counts_.at(dead.owner)=static_cast<std::uint8_t>(active_counts_.at(dead.owner)-1U);
        if (turn_.controllers.at(dead.owner)==0) death_counter_27c_=increment32(death_counter_27c_);
        else death_counter_278_=increment32(death_counter_278_);
    }
    for (std::size_t i=0;i<combat_.size();++i) {
        units_[i].active=combat_[i].active;
        units_[i].timer_ms=combat_[i].timer_30_ms;
        synchronize_unit(i);
    }
    if (selected_ && !units_[*selected_].active) selected_.reset();
    battle_=std::move(presentation);
    ++next_battle_token_;
}

bool GameSession::attack_selected(std::size_t defender) {
    const auto targets=selected_attack_targets();
    if (std::find(targets.begin(),targets.end(),defender)==targets.end()) return false;
    begin_battle(*selected_,defender);
    return true;
}

void GameSession::report_battle_finished(std::uint64_t token) {
    if (!battle_ || battle_->token!=token)
        throw FormatError("stale native battle presentation response");
    battle_.reset();
}

std::optional<TurnTransition> GameSession::end_turn() {
    if (!end_turn_available()) return std::nullopt;
    const auto transition=advance_player_turn(world_.units,units_,captures_,
        {{signed_byte(world_.player_factions[0]),signed_byte(world_.player_factions[1])}},turn_);
    for (std::size_t index=0;index<units_.size();++index) synchronize_unit(index);
    clear_selection();
    return transition;
}

void GameSession::finish_ordinary_arrival(std::size_t index) {
    auto& state = units_.at(index);
    const auto& unit = world_.units.at(index);
    std::vector<ArrivalUnit> roster;
    for (std::size_t n=0; n<units_.size(); ++n) {
        const auto& other = world_.units[n];
        roster.push_back({other.type,other.owner,other.x,other.y,units_[n].facing,other.active});
    }
    const auto& form = world_.unit_definitions.at(unit.type).forms.at(unit.form);
    const auto arrival = choose_movement_arrival_facing(roster.at(index),roster,
        form.at(1),form.at(2),signed_byte(form.at(13)));
    if (arrival.writes_facing) state.facing = arrival.facing;
    // Admission requires an empty destination, so the actor cannot enter the
    // unresolved co-location/transport branch. No capture state is changed.
    synchronize_unit(index);
    moving_.reset();
    action_.reset();
}

void GameSession::apply_mission_effects(const MissionTickResult& result) {
    for (const auto effect : result.effects) {
        switch (effect) {
        case MissionEffect::reset_current_player_actions:
            if (moving_) throw FormatError("mission reset during a movement action");
            for (std::size_t n=0; n<units_.size(); ++n)
                if (world_.units[n].owner == turn_.current_player) {
                    reset_movement_turn(units_[n]);
                    synchronize_unit(n);
                }
            break;
        case MissionEffect::return_to_script_mode:
        case MissionEffect::enter_gameplay_mode:
            clear_selection();
            break;
        case MissionEffect::close_dialogue:
        case MissionEffect::skip_dialogue_audio_event:
            // Explicitly returned to the UI/audio host by SessionTick.
            break;
        }
    }
}

SessionTick GameSession::tick(std::uint32_t delta_ms, const MissionTickInput& input) {
    SessionTick result;
    if (battle_) return result;
    if (moving_) {
        const auto index = *moving_;
        const auto movement = action_->advance_tick(delta_ms);
        units_[index] = action_->state();
        synchronize_unit(index);
        result.world_changed = true;
        if (movement == MovementTickResult::completed) {
            finish_ordinary_arrival(index);
            result.movement_finished = true;
        }
    }
    result.mission = mission_.tick(delta_ms,input);
    apply_mission_effects(result.mission);
    if (!moving_ && (mission_.state().gate == MissionGate::captured_site_item ||
                    mission_.state().gate == MissionGate::objective)) {
        const auto observed = mission_.observe_objective(captures_.sites,objective_units(),
                                                         campaign_context(),turn_.current_player);
        apply_mission_effects(observed);
        result.mission.effects.insert(result.mission.effects.end(),observed.effects.begin(),observed.effects.end());
    }
    if (mission_.state().stop == MissionStop::completion_presentation_required)
        result.completion=mission_.begin_completion(mission_.state().command_index,campaign_context());
    return result;
}

void GameSession::report_camera(std::size_t command_index, bool reached) {
    mission_.report_camera(command_index,reached);
}

std::uint32_t SimulationClock::add_elapsed(std::uint32_t elapsed_ms) noexcept {
    const auto total = remainder_ms_ + std::min(elapsed_ms,std::uint32_t(1000));
    remainder_ms_ = total % step_ms;
    return total / step_ms;
}
} // namespace g1
