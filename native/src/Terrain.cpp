#include "g1/Terrain.hpp"

#include <algorithm>
#include <limits>

namespace g1 {
namespace {

void validate_grid(const TerrainGrid& grid) {
    if (grid.width == 0 || grid.width > 255 || grid.height == 0 || grid.height > 255)
        throw FormatError("terrain grid dimensions must be 1..255");
    if (grid.tiles.size() != static_cast<std::size_t>(grid.width) * grid.height)
        throw FormatError("terrain grid payload does not match dimensions");
    for (const auto tile : grid.tiles)
        if (tile > 31 && tile != 255)
            throw FormatError("terrain tile is outside the observed table or empty sentinel");
}

std::int16_t narrow_position(std::int64_t value) {
    if (value < std::numeric_limits<std::int16_t>::min() ||
        value > std::numeric_limits<std::int16_t>::max())
        throw FormatError("terrain coordinate exceeds the supported signed16 range");
    return static_cast<std::int16_t>(value);
}

std::array<std::int16_t, 3> position(std::int64_t x, std::int64_t y, std::int64_t z) {
    return {narrow_position(x), narrow_position(y), narrow_position(z)};
}

std::array<std::array<std::int16_t, 2>, 4> cell_uv(std::uint8_t cell) {
    if (cell >= 32) throw FormatError("terrain atlas cell exceeds 8x4 atlas");
    // Original 0x714c0 uses the WIDTH-derived inset on both texture axes.
    const int u = (cell % 8) * 8192 - 32768;
    const int v = (cell / 8) * 16384 - 32768;
    constexpr int inset = 128;
    return {{{static_cast<std::int16_t>(u + inset), static_cast<std::int16_t>(v + inset)},
             {static_cast<std::int16_t>(u + inset), static_cast<std::int16_t>(v + 16384 - inset - 1)},
             {static_cast<std::int16_t>(u + 8192 - inset - 1), static_cast<std::int16_t>(v + inset)},
             {static_cast<std::int16_t>(u + 8192 - inset - 1),
              static_cast<std::int16_t>(v + 16384 - inset - 1)}}};
}

TerrainQuad make_quad(TerrainFace face, std::uint8_t cell,
                       const std::array<std::array<std::int16_t, 3>, 4>& positions) {
    TerrainQuad result{};
    result.face = face;
    result.atlas_cell = cell;
    result.positions = positions;
    result.quantized_uv = cell_uv(cell);
    // 0x71884 mode1, with the single-cell subdivision ratio exactly1.
    constexpr float bias = 0.50000762939453125F; // Original bits 0x3f000080.
    constexpr float scale = 1.0F / 65535.0F;
    for (std::size_t i = 0; i < 4; ++i)
        for (std::size_t j = 0; j < 2; ++j)
            result.normalized_uv[i][j] = static_cast<float>(result.quantized_uv[i][j]) * scale + bias;
    return result;
}

} // namespace

std::uint8_t TerrainGrid::tile_at(std::uint16_t x, std::uint16_t y) const {
    if (width == 0 || height == 0 || width > 255 || height > 255 ||
        tiles.size() != static_cast<std::size_t>(width) * height ||
        x >= width || y >= height)
        throw FormatError("terrain grid coordinate or shape is invalid");
    return tiles[static_cast<std::size_t>(y) * width + x];
}

TerrainGrid decode_terrain_grid(const Bytes& bytes) {
    if (bytes.size() < 2) throw FormatError("terrain grid header is truncated");
    if (bytes.size() != 2 + static_cast<std::size_t>(bytes[0]) * bytes[1])
        throw FormatError("terrain grid payload does not match dimensions");
    TerrainGrid result{bytes[0], bytes[1], Bytes(bytes.begin() + 2, bytes.end())};
    validate_grid(result);
    return result;
}

TerrainLookup decode_terrain_lookup(const Bytes& bytes) {
    if (bytes.size() != 33 || bytes[0] != 1)
        throw FormatError("terrain lookup requires observed marker 1 and 32 entries");
    TerrainLookup result{};
    std::copy(bytes.begin() + 1, bytes.end(), result.begin());
    return result;
}

TerrainRules decode_terrain_rules(const Bytes& bytes) {
    if (bytes.empty() || bytes[0] == 0) throw FormatError("terrain rules require counted rows");
    const auto count = static_cast<std::size_t>(bytes[0]);
    if (bytes.size() != 1 + count * 4)
        throw FormatError("terrain rule count does not match three-byte rows");
    TerrainRules result;
    result.reserve(count);
    for (std::size_t i = 0; i < count; ++i) {
        const auto offset = 1 + i * 4;
        if (bytes[offset] != 3) throw FormatError("terrain rule row width is unsupported");
        result.push_back({{bytes[offset + 1], bytes[offset + 2], bytes[offset + 3]}});
    }
    return result;
}

TerrainTables decode_terrain_tables(const Bytes& bytes) {
    if (bytes.size() != 480) throw FormatError("terrain visual tables require exactly 480 data bytes");
    TerrainTables result{};
    std::size_t offset = 0;
    for (auto& style : result) {
        for (auto& record : style) {
            for (auto& cell : record.atlas_cells) {
                cell = bytes[offset++];
                if (cell >= 32) throw FormatError("terrain table has an unsupported atlas selector");
            }
            const auto raw = bytes[offset++];
            record.height_steps = static_cast<std::int8_t>(raw < 128 ? raw : static_cast<int>(raw) - 256);
        }
    }
    return result;
}

std::uint32_t terrain_atlas_resource(std::uint8_t style) {
    constexpr std::array<std::uint32_t, 3> ids{693, 777, 761};
    if (style >= ids.size()) throw FormatError("terrain style is outside the recovered table");
    return ids[style];
}

std::vector<TerrainQuad> terrain_cell_quads(const TerrainCellShape& shape,
                                           const TerrainVisualRecord& record) {
    constexpr std::uint8_t valid_mask = 0x1b;
    if ((shape.face_mask & ~valid_mask) != 0 || (shape.previous_mask & ~valid_mask) != 0)
        throw FormatError("terrain face mask contains an unsupported bit");
    for (const auto cell : record.atlas_cells)
        if (cell >= 32) throw FormatError("terrain cell contains an unsupported atlas selector");
    const std::int64_t x0 = static_cast<std::int64_t>(shape.origin_x) +
        ((shape.bevel && (shape.previous_mask & 2)) ? 16 : 0);
    const std::int64_t x1 = static_cast<std::int64_t>(shape.origin_x) + 32;
    const std::int64_t z0 = shape.origin_z, z1 = z0 + 32;
    const auto low_left = x0 - ((shape.bevel && (shape.face_mask & 8)) ? 16 : 0);
    const auto low_right = x1 + ((shape.bevel && (shape.face_mask & 2)) ? 16 : 0);
    const auto top = shape.top, bottom = shape.bottom;
    std::vector<TerrainQuad> result;
    result.reserve(4);
    // Preserve original append order, which differs from record field order.
    if (shape.face_mask & 1)
        result.push_back(make_quad(TerrainFace::front, record.atlas_cells[1],
            {position(x0, top, z1), position(low_left, bottom, z1),
             position(x1, top, z1), position(low_right, bottom, z1)}));
    if (shape.face_mask & 2)
        result.push_back(make_quad(TerrainFace::right, record.atlas_cells[3],
            {position(x1, top, z1), position(low_right, bottom, z1),
             position(x1, top, z0), position(low_right, bottom, z0)}));
    if (shape.face_mask & 8)
        result.push_back(make_quad(TerrainFace::left, record.atlas_cells[2],
            {position(x0, top, z0), position(low_left, bottom, z0),
             position(x0, top, z1), position(low_left, bottom, z1)}));
    if (shape.face_mask & 16)
        result.push_back(make_quad(TerrainFace::top, record.atlas_cells[0],
            {position(x0, top, z0), position(x0, top, z1),
             position(x1, top, z0), position(x1, top, z1)}));
    return result;
}

TerrainMesh build_terrain_mesh(const TerrainGrid& grid, const TerrainTables& tables,
                               std::uint8_t style) {
    validate_grid(grid);
    const auto atlas = terrain_atlas_resource(style);
    if (style == 1)
        throw FormatError("style 1 animated-terrain routing is not yet implemented");
    if (std::find(grid.tiles.begin(), grid.tiles.end(), 255) != grid.tiles.end())
        throw FormatError("empty-sentinel terrain mesh routing is outside the observed grid corpus");
    const auto& visuals = tables[style];
    TerrainMesh result{style, atlas, 0.01F, {}};
    result.quads.reserve(grid.tiles.size() * 2);
    for (std::uint16_t y = 0; y < grid.height; ++y) {
        std::uint8_t previous = 0x10;
        for (std::uint16_t x = 0; x < grid.width; ++x) {
            const auto tile = grid.tile_at(x, y);
            const auto& record = visuals[tile];
            const auto h = static_cast<std::int32_t>(record.height_steps);
            std::uint8_t mask = 0x10;
            std::int32_t low = 0;
            const auto lower_neighbor = [&](std::uint8_t neighbor, std::uint8_t bit) {
                if (neighbor != 255 && h > visuals[neighbor].height_steps) {
                    mask = static_cast<std::uint8_t>(mask | bit);
                    low = std::min(low, static_cast<std::int32_t>(visuals[neighbor].height_steps));
                }
            };
            if (x > 0) lower_neighbor(grid.tile_at(x - 1, y), 8);
            if (y + 1 < grid.height) lower_neighbor(grid.tile_at(x, y + 1), 1);
            else if (style == 0) lower_neighbor(13, 1);
            if (x + 1 < grid.width) lower_neighbor(grid.tile_at(x + 1, y), 2);
            const TerrainCellShape shape{static_cast<std::int32_t>(x) * 32,
                static_cast<std::int32_t>(y) * 32, h * 32, low * 32, mask, previous, style == 0};
            auto quads = terrain_cell_quads(shape, record);
            for (auto& quad : quads) { quad.tile_x = x; quad.tile_y = y; }
            result.quads.insert(result.quads.end(), quads.begin(), quads.end());
            previous = mask;
        }
    }
    return result;
}

} // namespace g1
