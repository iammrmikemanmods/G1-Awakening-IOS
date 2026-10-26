#pragma once

#include "g1/Text.hpp"
#include "g1/World.hpp"

namespace g1 {

// Values supplied by the text renderer, not guessed from the character count.
// Original font virtual methods +8 and +12 supply metric_a and metric_b.
struct DialogueLayout {
    std::int32_t line_count{};
    std::int32_t line_height{};
    std::int32_t metric_a{};
    std::int32_t metric_b{};
    std::int32_t box_height{};
    bool visible_text_fully_revealed{}; // Original draw result map+0x1fc.
};

struct DialogueProgress {
    std::int32_t first_line{};
    std::int32_t reveal_offset{-65536000}; // Original map+0x26c.
    bool ready_for_next_command{};
    bool skip_following_dialogue{};
};

struct DialogueUpdate {
    DialogueProgress progress;
    std::uint32_t remaining_input_edges{};
    bool more_pages{};
    bool skip_audio_event{}; // Original 0x2ad12(app, 5, 18) request.
};

// Direct translation of 0x4e3bc, including 0x2b9c2's consume-on-first-match
// input behavior. Masks: 1 back, 16/64 advance, 128 skip. A match clears the
// whole edge word, so simultaneous bits are not independent button presses.
// No input gesture, layout, font, text drawing or audio is synthesized here.
DialogueUpdate advance_dialogue(const DialogueProgress&, const DialogueLayout&,
                                std::uint32_t input_edges, std::uint32_t delta_ms);

// Original draw-side character budget at 0x5b9aa..0x5b9ae. The renderer still
// determines page clipping and whether all visible text has been drawn.
std::int32_t dialogue_character_budget(const DialogueProgress&) noexcept;

struct MissionSiteState {
    std::int8_t state{-1};
    std::vector<std::vector<std::int8_t>> item_states;
};

// Separate from site coordinates: map+0x3e8 is site state, map+0x3f8 is nested
// item state, and opcode 7 initializes both to -1. A real capture action must
// update these values; merely moving to a coordinate does not satisfy a goal.
std::vector<MissionSiteState> initial_mission_site_states(const WorldBootstrap&);

struct CapturedSiteObjective {
    std::int16_t site{};
    std::int16_t group{};
    std::int16_t item{};
    std::int16_t desired_state{};
    std::int16_t text_index{};
    std::uint16_t text_id{};
};

// Recovered kind-1 branch 0x55a90..0x55b6c. If ANY index is -1 the original
// compares ALL sites and ALL items, including each site's own state; it does
// not retain the other two index filters. Other negative/out-of-range indices
// are rejected rather than reproducing the original unchecked pointer access.
bool captured_site_objective_satisfied(const CapturedSiteObjective&,
                                      const std::vector<MissionSiteState>&);

struct MissionDialogue {
    std::int16_t speaker_type{}; // -1 is the original tutorial-heading branch.
    std::int16_t text_index{};
    std::uint16_t text_id{};
    std::uint16_t heading_text_id{};
    DialogueProgress progress;
};

enum class MissionGate {
    dialogue,
    camera,
    delay,
    transition,
    captured_site_item,
    advance_pending,
    stopped,
    end_of_stream,
};

enum class MissionStop {
    none,
    unsupported_command,
    unsupported_objective,
    unsupported_player_loss_branch,
    completion_presentation_required,
    campaign_handoff_required,
};

enum class MissionEffect {
    close_dialogue,
    skip_dialogue_audio_event, // 0x2ad12(app, 5, 18).
    enter_gameplay_mode,      // Original 0x553ee; broader gameplay setup external.
    reset_current_player_actions, // 0x55840(false) -> 0x430fc per current-player unit.
    return_to_script_mode,
};

struct MissionExecutionState {
    std::size_t command_index{};
    std::uint16_t opcode{};
    std::int32_t original_phase{}; // 99 is pending advance while in script mode.
    std::uint8_t interaction_mode{6}; // 6 script, 0 gameplay; goal gate suspends script ticks.
    MissionGate gate{MissionGate::stopped};
    MissionStop stop{MissionStop::none};
    std::string stop_detail;
    bool phase_flag_225{};
    bool skip_following_dialogue{};
    std::int32_t transition_value{};
    std::int32_t remaining_delay_ms{};
    // Only the active gate should be presented. As in the original direct
    // end-of-stream -> gameplay path, backing dialogue data may outlive it.
    std::optional<MissionDialogue> dialogue;
    std::optional<WorldCameraRequest> camera;
    std::optional<CapturedSiteObjective> objective;
    std::optional<std::uint16_t> pending_text_id;
};

struct MissionTickInput {
    std::uint32_t input_edges{};
    std::optional<DialogueLayout> dialogue_layout;
};

struct MissionTickResult {
    std::uint32_t remaining_input_edges{};
    std::vector<MissionEffect> effects;
};

// Native control-flow continuation for the cold first-campaign bootstrap.
// It owns no renderer, audio, combat, save system or original machine code.
// It starts at the bootstrap's unconsumed cursor 9 and returns typed requests.
// Clients must implement the returned effects; receiving an effect is not
// evidence that its gameplay/UI work has been performed.
//
// tick() performs one original phase update. Phase 99 advances the cursor on
// the following tick, without carrying unused delay time into another command.
// Camera callbacks are explicit because 0x557f4 delegates completion to the
// renderer. Goal observations are separate from clock ticks, as in the game.
// Opcode 8 completion presentation and opcode 10 campaign handoff stop before
// consumption. No API labels this partial flow as a completed mission.
class MissionExecution {
public:
    explicit MissionExecution(const WorldBootstrap&);
    const MissionExecutionState& state() const noexcept { return state_; }
    MissionTickResult tick(std::uint32_t delta_ms, const MissionTickInput& = {});

    // The command token prevents a stale renderer response from completing a
    // later camera request. false retains the current camera gate.
    void report_camera(std::size_t command_index, bool reached);

    // Implements the regular first-campaign goal branch. Player-loss/alternate
    // campaign branches stop explicitly. These counts must come from real
    // active units, and the item state from actual native capture behavior.
    MissionTickResult observe_objective(const std::vector<MissionSiteState>&,
                                       std::array<std::uint8_t, 2> active_unit_counts);

private:
    std::vector<MissionCommand> commands_;
    std::vector<std::uint16_t> raw_unit_name_indices_;
    MissionExecutionState state_;
    void enter_current(std::vector<MissionEffect>&);
    void stop(MissionStop, const std::string&);
};

} // namespace g1
