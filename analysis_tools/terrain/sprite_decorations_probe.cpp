// Development-only typed stdin/stdout adapter; no original code execution.
#include "g1/TerrainSpriteDecorations.hpp"
#include "g1/Combat.hpp"

#include <algorithm>
#include <cstring>
#include <iostream>
#include <string>
#include <utility>

namespace {
std::uint32_t number() {
    std::uint32_t n{};
    if (!(std::cin >> n)) throw g1::FormatError("short terrain sprite probe input");
    return n;
}
g1::Bytes bytes() {
    const auto n = number();
    if (n > 65535) throw g1::FormatError("terrain sprite input exceeds its byte-vector bound");
    g1::Bytes out;
    out.reserve(n);
    for (std::uint32_t i = 0; i < n; ++i) {
        const auto value = number();
        if (value > 255) throw g1::FormatError("terrain sprite input byte exceeds255");
        out.push_back(static_cast<std::uint8_t>(value));
    }
    return out;
}
template<class R> void numbers(const R& values) {
    bool first = true;
    std::cout << '[';
    for (const auto value : values) { if (!first) std::cout << ','; first = false; std::cout << +value; }
    std::cout << ']';
}
void snapshot(const g1::TerrainSpriteDecorationLayout& layout,
              const g1::TerrainSpriteAnimationBank& bank,
              const g1::TerrainSpriteDecorationState& state, const g1::GameRandom& random) {
    std::cout << "{\"candidate_records\":"; numbers(state.candidate_records);
    std::cout << ",\"slot_phases\":"; numbers(state.slot_phases);
    std::cout << ",\"sprites\":[";
    for (std::size_t i = 0; i < state.sprites.size(); ++i) {
        if (i) std::cout << ',';
        const auto& sprite = state.sprites[i];
        const auto& p = sprite.playback;
        const auto frame = bank[layout.selectors[i] - 73U][sprite.animation_index][p.step_index].frame_index;
        std::cout << "{\"index\":" << i + 4 << ",\"selector\":" << +layout.selectors[i]
                  << ",\"animation\":" << +sprite.animation_index
                  << ",\"visible\":" << sprite.visible << ",\"enabled\":" << sprite.visible
                  << ",\"parent\":" << unsigned(sprite.parent)
                  << ",\"attachment_order\":" << sprite.attachment_order << ",\"position\":";
        if (sprite.original_position) numbers(*sprite.original_position); else std::cout << "null";
        std::cout << ",\"playback\":[" << p.step_index << ',' << +frame << ',' << p.elapsed_ms << ','
                  << p.repeat_count << ',' << p.reverse << ',' << p.completed << "]}";
    }
    std::cout << "],\"accumulated_ms\":" << state.accumulated_ms << ",\"phase\":" << +state.phase
              << ",\"random_index\":" << random.state().index
              << ",\"random_draws\":" << random.state().draws << ",\"random_words\":";
    numbers(random.state().words);
    std::cout << '}';
}
}

int main() {
    try {
        std::string magic;
        std::cin >> magic;
        if (magic != "G1_TERRAIN_SPRITE_INPUT_V1") throw g1::FormatError("wrong terrain sprite input magic");
        const auto seed = number(), style = number();
        if (style > 2) throw g1::FormatError("invalid terrain sprite style");
        const auto grid = g1::decode_terrain_grid(bytes());
        const auto tables = g1::decode_terrain_tables(bytes());
        const auto config = g1::decode_terrain_animation_config(bytes());
        const auto raw_lookup = bytes();
        if (raw_lookup.size() != 32) throw g1::FormatError("terrain sprite lookup must contain32 entries");
        g1::TerrainLookup lookup{};
        std::copy(raw_lookup.begin(), raw_lookup.end(), lookup.begin());
        g1::TerrainSpriteAnimationBank bank;
        for (auto& animations : bank) {
            const auto count = number();
            if (count > 255) throw g1::FormatError("too many sprite animations");
            for (std::uint32_t a = 0; a < count; ++a) {
                const auto step_count = number();
                if (step_count > 255) throw g1::FormatError("too many sprite animation steps");
                std::vector<g1::AtlasStep> steps;
                for (std::uint32_t s = 0; s < step_count; ++s) {
                    const auto frame = number(), duration = number();
                    if (frame > 255 || duration > 65535) throw g1::FormatError("invalid sprite step");
                    steps.push_back({static_cast<std::uint8_t>(frame), static_cast<std::uint16_t>(duration)});
                }
                animations.push_back(std::move(steps));
            }
        }
        const auto layout = g1::build_terrain_sprite_decoration_layout(grid, tables, config, lookup,
                                                                       static_cast<std::uint8_t>(style));
        g1::GameRandom random(seed);
        auto state = g1::create_terrain_sprite_decorations(layout, bank, random);
        const auto count = number();
        if (count > 4096) throw g1::FormatError("terrain sprite tick bound exceeded");
        std::cout << "{\"layout\":{\"candidate_capacity\":" << layout.initial_candidate_records.size() / 3
                  << ",\"registered_candidates\":" << layout.registered_candidates
                  << ",\"slot_count\":" << state.slot_phases.size()
                  << ",\"fixed_sprite_capacity\":" << layout.fixed_sprite_capacity
                  << ",\"original_sprite_count\":" << layout.selectors.size() + 4
                  << ",\"initial_candidate_records\":";
        numbers(layout.initial_candidate_records);
        std::cout << "},\"snapshots\":[";
        snapshot(layout, bank, state, random);
        for (std::uint32_t i = 0; i < count; ++i) {
            g1::advance_terrain_sprite_decorations(layout, bank, state, number(), random);
            std::cout << ',';
            snapshot(layout, bank, state, random);
        }
        std::cout << "],\"draws\":[";
        bool first = true;
        for (const auto& draw : g1::terrain_sprite_decoration_draws(layout, bank, state)) {
            if (!first) std::cout << ',';
            first = false;
            std::cout << "{\"index\":" << draw.original_index << ",\"descriptor\":" << draw.resource.descriptor_id
                      << ",\"image\":" << draw.resource.image_id << ",\"key\":" << draw.resource.resource_key
                      << ",\"frame\":" << +draw.frame_index << ",\"parent\":" << unsigned(draw.parent)
                      << ",\"attachment_order\":" << draw.attachment_order
                      << ",\"model_bits\":";
            std::array<std::uint32_t, 16> bits{};
            std::memcpy(bits.data(), draw.model.data(), sizeof(bits));
            numbers(bits);
            std::cout << '}';
        }
        std::cout << "]}\n";
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
    return 0;
}
