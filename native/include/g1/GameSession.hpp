#pragma once

#include "g1/MissionExecution.hpp"
#include "g1/MovementAction.hpp"
#include "g1/MovementArrival.hpp"
#include "g1/CaptureAction.hpp"
#include "g1/Combat.hpp"
#include "g1/TransformAction.hpp"
#include "g1/TurnProgression.hpp"

#include <memory>

namespace g1 {

enum class MoveRequestResult {
    started, script_controls_input, computer_controls_input, movement_in_progress, no_selected_unit,
    inactive_unit, other_player, action_used, already_moved,
    outside_map, occupied_destination, no_route,
};

struct SessionTick {
    MissionTickResult mission;
    std::optional<CompletionPresentation> completion;
    bool movement_finished{};
    bool world_changed{};
};

struct SessionBattle {
    std::uint64_t token{};
    std::size_t attacker{},defender{};
    CombatUnitState attacker_before,defender_before;
    CombatExchange exchange;
};

// Native integration of recovered mission, movement, capture, transformation
// and combat state. Host presentation acknowledgements never replace actual
// gameplay state or establish a completed campaign.
class GameSession {
public:
    explicit GameSession(WorldBootstrap, std::uint32_t random_seed, CampaignContext = {});
    const WorldBootstrap& world() const noexcept { return world_; }
    const MissionExecutionState& mission() const noexcept { return mission_.state(); }
    const std::vector<MovementUnitState>& units() const noexcept { return units_; }
    const std::vector<MissionSiteState>& sites() const noexcept { return captures_.sites; }
    const CaptureNetwork& captures() const noexcept { return captures_; }
    const std::vector<CombatUnitState>& combat_units() const noexcept { return combat_; }
    const std::optional<std::size_t>& selected() const noexcept { return selected_; }
    std::uint8_t current_player() const noexcept { return turn_.current_player; }
    const TurnState& turn() const noexcept { return turn_; }
    CampaignContext campaign_context() const;
    MissionRecord mission_record() const noexcept;
    const std::optional<SessionBattle>& battle() const noexcept { return battle_; }
    bool moving() const noexcept { return moving_.has_value(); }

    // Selection is a native UI operation. Command admission still enforces
    // original active/current-player/action/spent rules before a move starts.
    bool select(std::size_t unit_index);
    void clear_selection() noexcept;
    std::optional<MovementRange> selected_movement_range() const;
    MoveRequestResult move_selected_to(WorldCoordinate);
    bool selected_can_capture() const;
    CaptureResult capture_selected();
    TransformEligibility selected_transform_eligibility() const;
    std::optional<TransformResult> transform_selected();
    std::vector<std::size_t> selected_attack_targets() const;
    bool attack_selected(std::size_t defender);
    // Called only after the host actually completes this battle presentation.
    // A stale token cannot unlock input for a later exchange.
    void report_battle_finished(std::uint64_t token);
    std::uint8_t transform_animation_pending(std::size_t index) const { return animation_pending_.at(index); }
    void clear_transform_animation_request(std::size_t index) { animation_pending_.at(index)=0; }
    bool end_turn_available() const;
    std::optional<TurnTransition> end_turn();

    // One simulation update. The host supplies elapsed time independently of
    // its display refresh. MovementAction remains fixed-distance per update.
    SessionTick tick(std::uint32_t delta_ms, const MissionTickInput& = {});
    void report_camera(std::size_t command_index, bool reached);

private:
    WorldBootstrap world_;
    CampaignContext campaign_;
    MissionExecution mission_;
    std::vector<MovementUnitState> units_;
    CaptureNetwork captures_;
    std::vector<CombatUnitState> combat_;
    std::vector<std::uint8_t> animation_pending_;
    GameRandom random_;
    std::optional<std::size_t> selected_, moving_;
    std::unique_ptr<MovementAction> action_;
    TurnState turn_;
    std::optional<SessionBattle> battle_;
    std::uint64_t next_battle_token_{1};
    std::int32_t death_counter_278_{},death_counter_27c_{};
    // Original map+0x7c bytes count activations, including repeated placement
    // of an already-active type. They cannot be derived from unique units.
    std::array<std::uint8_t,2> active_counts_{};
    std::vector<std::array<std::int32_t,4>> death_log_;

    void synchronize_unit(std::size_t);
    void apply_mission_effects(const MissionTickResult&);
    void finish_ordinary_arrival(std::size_t);
    std::vector<MissionObjectiveUnit> objective_units() const;
    CombatRulesView combat_rules() const;
    void begin_battle(std::size_t attacker,std::size_t defender);
};

// Native scheduling policy based on the observed original 30ms timer request.
// It makes the simulation independent of 60Hz drawing. The original's one-shot
// callback overhead is not inferred as an exact wall-clock 33.333Hz guarantee.
// Reset on background/resume; do not run catch-up turns while the app is away.
class SimulationClock {
public:
    static constexpr std::uint32_t step_ms = 30;
    std::uint32_t add_elapsed(std::uint32_t elapsed_ms) noexcept;
    float interpolation() const noexcept { return remainder_ms_ / float(step_ms); }
    void reset() noexcept { remainder_ms_ = 0; }
private:
    std::uint32_t remainder_ms_{};
};

} // namespace g1
