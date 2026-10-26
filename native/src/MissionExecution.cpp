#include "g1/MissionExecution.hpp"

#include <algorithm>
#include <limits>

namespace g1 {
namespace {

std::int32_t signed32(std::uint32_t value) noexcept {
    return value <= 0x7fffffffU ? static_cast<std::int32_t>(value) :
        static_cast<std::int32_t>(static_cast<std::int64_t>(value) - 0x100000000LL);
}

std::int32_t wrap32(std::int64_t value) noexcept {
    return signed32(static_cast<std::uint32_t>(value));
}

std::int16_t signed16(std::uint16_t value) noexcept {
    const auto wide = value <= 0x7fffU ? static_cast<std::int32_t>(value) :
        static_cast<std::int32_t>(value) - 0x10000;
    return static_cast<std::int16_t>(wide);
}

std::int64_t floor_div_65536(std::int64_t value) noexcept {
    return value >= 0 ? value / 65536 : -((-value + 65535) / 65536);
}

// Original 0x2b644 takes a signed Q16.16 delta and multiplier. The preceding
// LSL #16 discards high bits; the low 32-bit result is preserved explicitly.
std::int32_t scaled_delta(std::uint32_t delta, std::int32_t multiplier) noexcept {
    const auto shifted = signed32(delta << 16U);
    return wrap32(floor_div_65536(static_cast<std::int64_t>(shifted) * multiplier));
}

bool consume_edge(std::uint32_t& edges, std::uint32_t mask) noexcept {
    if ((edges & mask) == 0U) return false;
    edges = 0U;
    return true;
}

void require_words(const MissionCommand& command, std::size_t count) {
    if (command.argument_words_u16.size() != count)
        throw FormatError("mission execution received a malformed decoded command");
}

void mark_ready(MissionExecutionState& state) noexcept {
    state.original_phase = 99;
    state.gate = MissionGate::advance_pending;
}

} // namespace

DialogueUpdate advance_dialogue(const DialogueProgress& input,
                                const DialogueLayout& layout,
                                std::uint32_t edges, std::uint32_t delta_ms) {
    if (layout.line_count < 0 || layout.line_height <= 0 || layout.box_height < 0 ||
        input.first_line < 0 || input.first_line > layout.line_count)
        throw FormatError("invalid dialogue layout or line cursor");
    if (input.ready_for_next_command)
        throw FormatError("cannot tick a completed dialogue gate");

    DialogueUpdate result;
    result.progress = input;
    auto& progress = result.progress;
    if (progress.reveal_offset < 0) {
        progress.reveal_offset = wrap32(static_cast<std::int64_t>(progress.reveal_offset) +
                                      scaled_delta(delta_ms, 2048));
        if (progress.reveal_offset > 0) progress.reveal_offset = 0;
    }
    const auto remaining = layout.line_count - progress.first_line;
    const auto height = wrap32(static_cast<std::int64_t>(remaining - 1) *
                              layout.line_height +
                              wrap32(static_cast<std::int64_t>(layout.metric_a) - layout.metric_b));
    result.more_pages = remaining > 0 && height >= layout.box_height;

    const bool back = consume_edge(edges, 1U);
    const bool advance = consume_edge(edges, 16U) || consume_edge(edges, 64U);
    const bool skip = consume_edge(edges, 128U);
    if (back || advance) {
        if (progress.first_line > 0 && back) {
            --progress.first_line;
        } else if (result.more_pages && advance) {
            const auto numerator = wrap32(static_cast<std::int64_t>(layout.box_height) + layout.metric_b);
            const auto lines = std::min(numerator / layout.line_height, remaining);
            if (lines < 0) throw FormatError("dialogue metrics produce a negative page step");
            progress.first_line += lines;
        } else if (!layout.visible_text_fully_revealed) {
            progress.reveal_offset = 0;
        } else if (!result.more_pages && advance) {
            progress.ready_for_next_command = true;
        }
    } else if (skip) {
        progress.ready_for_next_command = true;
        progress.skip_following_dialogue = true;
        result.skip_audio_event = true;
    }
    result.remaining_input_edges = edges;
    return result;
}

std::int32_t dialogue_character_budget(const DialogueProgress& progress) noexcept {
    return static_cast<std::int32_t>(1000 + floor_div_65536(progress.reveal_offset));
}

std::vector<MissionSiteState> initial_mission_site_states(const WorldBootstrap& world) {
    std::vector<MissionSiteState> result;
    result.reserve(world.sites.size());
    for (const auto& site : world.sites) {
        MissionSiteState state;
        state.state = site.state;
        for (const auto& group : site.coordinate_groups)
            state.item_states.emplace_back(group.size(), static_cast<std::int8_t>(-1));
        result.push_back(std::move(state));
    }
    return result;
}

bool captured_site_objective_satisfied(const CapturedSiteObjective& objective,
                                      const std::vector<MissionSiteState>& sites) {
    if (objective.site < -1 || objective.group < -1 || objective.item < -1)
        throw FormatError("unsupported negative capture-objective index");
    if (objective.site == -1 || objective.group == -1 || objective.item == -1) {
        for (const auto& site : sites) {
            if (site.state != objective.desired_state) return false;
            for (const auto& group : site.item_states)
                for (const auto item : group)
                    if (item != objective.desired_state) return false;
        }
        return true;
    }
    const auto site_index = static_cast<std::size_t>(objective.site);
    const auto group_index = static_cast<std::size_t>(objective.group);
    const auto item_index = static_cast<std::size_t>(objective.item);
    if (site_index >= sites.size() || group_index >= sites[site_index].item_states.size() ||
        item_index >= sites[site_index].item_states[group_index].size())
        throw FormatError("capture-objective index exceeds native site state");
    return sites[site_index].item_states[group_index][item_index] == objective.desired_state;
}

MissionExecution::MissionExecution(const WorldBootstrap& world)
    : commands_(world.commands) {
    if (world.mission_resource_id != 315U ||
        world.stop != BootstrapStop::presentation_required ||
        world.next_command_index >= commands_.size() ||
        commands_[world.next_command_index].opcode != 3U)
        throw FormatError("mission continuation requires the cold first-campaign dialogue boundary");
    raw_unit_name_indices_.reserve(world.unit_definitions.size());
    for (std::size_t type = 0; type < world.unit_definitions.size(); ++type) {
        const auto& definition = world.unit_definitions[type];
        if (definition.type != type)
            throw FormatError("mission speaker definitions are not indexed by unit type");
        raw_unit_name_indices_.push_back(definition.raw_text_indices[0]);
    }
    state_.command_index = world.next_command_index;
    state_.phase_flag_225 = world.flag_225;
    state_.original_phase = 99;
    std::vector<MissionEffect> effects;
    enter_current(effects);
    if (!effects.empty())
        throw FormatError("unexpected effect before initial dialogue presentation");
}

void MissionExecution::stop(MissionStop reason, const std::string& detail) {
    state_.gate = MissionGate::stopped;
    state_.stop = reason;
    state_.stop_detail = detail;
}

void MissionExecution::enter_current(std::vector<MissionEffect>& effects) {
    if (state_.command_index >= commands_.size()) {
        state_.gate = MissionGate::end_of_stream;
        state_.interaction_mode = 0U;
        effects.push_back(MissionEffect::enter_gameplay_mode);
        return;
    }
    const auto& command = commands_[state_.command_index];
    if (state_.command_index > 0U && commands_[state_.command_index - 1U].opcode == 3U &&
        command.opcode != 3U)
        effects.push_back(MissionEffect::close_dialogue);
    state_.opcode = command.opcode;
    state_.dialogue.reset();
    state_.camera.reset();
    state_.objective.reset();
    state_.pending_text_id.reset();
    const auto& args = command.argument_words_u16;
    switch (command.opcode) {
    case 3: {
        require_words(command, 2U);
        if (state_.skip_following_dialogue) { mark_ready(state_); return; }
        MissionDialogue dialogue;
        dialogue.speaker_type = signed16(args[0]);
        dialogue.text_index = signed16(args[1]);
        dialogue.text_id = script_text_id(dialogue.text_index);
        if (dialogue.speaker_type == -1) dialogue.heading_text_id = 0x019dU;
        else {
            if (dialogue.speaker_type < 0 ||
                static_cast<std::size_t>(dialogue.speaker_type) >= raw_unit_name_indices_.size())
                throw FormatError("dialogue speaker type is outside the recovered definitions");
            dialogue.heading_text_id = script_text_id(unit_text_index(
                raw_unit_name_indices_[static_cast<std::size_t>(dialogue.speaker_type)]));
        }
        state_.phase_flag_225 = false;
        state_.original_phase = 3;
        state_.gate = MissionGate::dialogue;
        state_.dialogue = dialogue;
        return;
    }
    case 4:
        require_words(command, 3U);
        state_.original_phase = 4;
        state_.camera = WorldCameraRequest{signed16(args[0]), signed16(args[1]), args[2] != 0U};
        state_.gate = MissionGate::camera;
        return;
    case 5:
        require_words(command, 1U);
        state_.original_phase = 5;
        state_.remaining_delay_ms = signed16(args[0]);
        state_.gate = MissionGate::delay;
        return;
    case 1:
    case 2:
        require_words(command, 0U);
        state_.phase_flag_225 = false;
        state_.transition_value = 0;
        state_.original_phase = command.opcode;
        state_.gate = MissionGate::transition;
        return;
    case 12: {
        if (args.size() != 6U || args[0] != 1U) {
            stop(MissionStop::unsupported_objective, "only original objective kind 1 is recovered here");
            return;
        }
        CapturedSiteObjective objective{signed16(args[2]), signed16(args[3]),
            signed16(args[4]), signed16(args[5]), signed16(args[1]),
            script_text_id(signed16(args[1]))};
        if (objective.site < -1 || objective.group < -1 || objective.item < -1)
            throw FormatError("unsupported negative objective index");
        state_.objective = objective;
        state_.gate = MissionGate::captured_site_item;
        state_.interaction_mode = 0U;
        state_.skip_following_dialogue = false; // Original cold path 0x5744c.
        // 0x56f5e does not write map+0x1e0. Script ticks are suspended by mode 0.
        effects.push_back(MissionEffect::enter_gameplay_mode);
        return;
    }
    case 8:
        require_words(command, 1U);
        state_.pending_text_id = script_text_id(signed16(args[0]));
        stop(MissionStop::completion_presentation_required,
             "opcode 8 requires its player-dependent completion presentation and audio handlers");
        return;
    case 10:
        require_words(command, 1U);
        stop(MissionStop::campaign_handoff_required,
             "opcode 10 save/profile and campaign handoff are not implemented");
        return;
    default:
        stop(MissionStop::unsupported_command, "mission command has no recovered continuation handler");
        return;
    }
}

MissionTickResult MissionExecution::tick(std::uint32_t delta_ms, const MissionTickInput& input) {
    MissionTickResult result{input.input_edges, {}};
    switch (state_.gate) {
    case MissionGate::advance_pending:
        ++state_.command_index;
        enter_current(result.effects);
        break;
    case MissionGate::dialogue: {
        if (!input.dialogue_layout)
            throw FormatError("dialogue tick requires actual renderer layout/reveal feedback");
        const auto update = advance_dialogue(state_.dialogue->progress,
            *input.dialogue_layout, input.input_edges, delta_ms);
        state_.dialogue->progress = update.progress;
        result.remaining_input_edges = update.remaining_input_edges;
        if (update.skip_audio_event) result.effects.push_back(MissionEffect::skip_dialogue_audio_event);
        if (update.progress.skip_following_dialogue) state_.skip_following_dialogue = true;
        if (update.progress.ready_for_next_command) mark_ready(state_);
        break;
    }
    case MissionGate::delay:
        state_.remaining_delay_ms = signed32(static_cast<std::uint32_t>(state_.remaining_delay_ms) - delta_ms);
        if (state_.remaining_delay_ms <= 0) mark_ready(state_);
        break;
    case MissionGate::transition: {
        const auto change = scaled_delta(delta_ms, 20000);
        if (state_.original_phase == 1) {
            state_.transition_value = wrap32(static_cast<std::int64_t>(state_.transition_value) + change);
            if (state_.transition_value >= 0) {
                state_.transition_value = 0;
                state_.phase_flag_225 = true;
                mark_ready(state_);
            }
        } else {
            state_.transition_value = wrap32(static_cast<std::int64_t>(state_.transition_value) - change);
            if (state_.transition_value < 0) {
                state_.transition_value = 0;
                mark_ready(state_);
            }
        }
        break;
    }
    case MissionGate::camera:
    case MissionGate::captured_site_item:
    case MissionGate::stopped:
    case MissionGate::end_of_stream:
        break;
    }
    return result;
}

void MissionExecution::report_camera(std::size_t command_index, bool reached) {
    if (state_.gate != MissionGate::camera || command_index != state_.command_index)
        throw FormatError("camera response does not match the pending mission command");
    if (reached) mark_ready(state_);
}

MissionTickResult MissionExecution::observe_objective(const std::vector<MissionSiteState>& sites,
                                                     std::array<std::uint8_t, 2> active_counts) {
    if (state_.gate != MissionGate::captured_site_item || !state_.objective)
        throw FormatError("objective observation without an active capture goal");
    MissionTickResult result;
    if (active_counts[0] == 0U || active_counts[1] == 0U) {
        stop(MissionStop::unsupported_player_loss_branch,
             "player-loss and alternate mission jumps require separate recovered behavior");
        return result;
    }
    if (captured_site_objective_satisfied(*state_.objective, sites)) {
        state_.interaction_mode = 6U;
        mark_ready(state_);
        result.effects.push_back(MissionEffect::reset_current_player_actions);
        result.effects.push_back(MissionEffect::return_to_script_mode);
    }
    return result;
}

} // namespace g1
