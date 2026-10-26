#pragma once

#include "g1/Mission.hpp"
#include "g1/Movement.hpp"
#include "g1/Terrain.hpp"

#include <array>
#include <optional>

namespace g1 {

// The original loader at 0x5a522 uses this resource-table order, which differs
// from archive order. Unknown scalar/stat meanings retain numbered fields.
struct UnitDefinition {
    std::uint8_t type{};
    std::uint32_t resource_id{};
    std::array<std::uint16_t, 2> raw_text_indices{};
    std::vector<std::uint16_t> raw_detail_text_indices;
    std::array<std::uint8_t, 5> scalar_fields{};
    Bytes auxiliary_fields;
    std::vector<Bytes> forms;

    // Original map+0x144[type], copied to unit+0xb before owner resolution.
    std::uint8_t faction() const noexcept { return scalar_fields[0]; }
};

UnitDefinition decode_unit_definition(const Bytes&, std::uint8_t type,
                                      std::uint32_t resource_id);
std::uint32_t unit_definition_resource(std::uint8_t type);
std::uint32_t campaign_mission_resource(std::size_t campaign_index);
std::uint32_t mission_grid_resource(std::size_t map_index);
std::uint32_t mission_lookup_resource(std::uint8_t style);
TerrainLookup apply_mission_style(const TerrainLookup& raw, std::uint8_t style);

struct WorldUnit {
    std::uint8_t type{};
    std::uint8_t faction{};
    std::uint8_t owner{};
    std::uint8_t form{};
    std::uint8_t x{};
    std::uint8_t y{};
    std::uint8_t spent_movement{};
    bool active{};
    std::size_t placement_command_index{};
};

struct WorldCoordinate {
    std::uint8_t x{};
    std::uint8_t y{};
};

// Opcode 7 stores sites and groups of coordinate pairs. Capture, production,
// triggers and the meaning of each group are not implemented by this type.
struct WorldSite {
    WorldCoordinate position;
    std::int8_t state{-1};
    std::vector<std::vector<WorldCoordinate>> coordinate_groups;
};

struct WorldCameraRequest {
    std::int16_t x{};
    std::int16_t y{};
    bool immediate{}; // Original opcode 4 interprets its third word as != 0.
};

enum class BootstrapStop {
    presentation_required,
    unsupported_command,
    end_of_stream,
};

struct WorldBootstrap {
    std::uint32_t mission_resource_id{};
    std::uint32_t grid_resource_id{};
    std::uint32_t lookup_resource_id{};
    std::uint8_t style{};
    TerrainGrid grid;
    TerrainLookup effective_lookup{};
    TerrainRules terrain_rules;
    std::vector<UnitDefinition> unit_definitions; // Indexed by original type.
    std::array<std::uint8_t, 2> player_factions{{0, 1}};
    std::array<bool, 23> available_types{};
    std::vector<WorldUnit> units; // Active placements, in command order.
    std::vector<WorldSite> sites;
    std::optional<WorldCameraRequest> camera;
    std::optional<std::uint16_t> title_text_index;
    std::uint16_t last_phase_opcode{};
    bool flag_225{}; // Original phase flag; broader semantics are unresolved.
    std::vector<MissionCommand> commands;
    std::size_t next_command_index{};
    BootstrapStop stop{BootstrapStop::end_of_stream};
    std::string stop_detail;

    // These construct inputs for the separately recovered native movement
    // rules. They neither execute a move nor advance the mission cursor.
    MovementBoard movement_board() const;
    MovementProfile movement_profile(std::size_t active_unit_index) const;
};

// Reconstructs the cold-start campaign entry selected by original 0x305ba:
// group 0, entry 0, player factions [0,1]. Extracts the proven gameplay state
// and presentation requests from the initial command prefix, then stops BEFORE
// the first dialogue/unsupported command. For the audited
// source this leaves cursor 9 at opcode 3; it is not a campaign executor.
// All resources come from Archive data. No original executable is opened.
WorldBootstrap bootstrap_first_campaign(const Archive&);

} // namespace g1
