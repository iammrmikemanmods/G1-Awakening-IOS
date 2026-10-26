#pragma once

#include "g1/Image.hpp"
#include "g1/SpriteGeometry.hpp"
#include "g1/World.hpp"

#include <map>

namespace g1 {

// Explicit 32-byte GPU layout. A Metal float3 has different alignment from
// SpriteVertex's packed 20-byte C++ layout, so the renderer converts here.
struct alignas(16) SceneVertex {
    std::array<float, 4> position;
    std::array<float, 2> uv;
    std::array<float, 2> padding{};
};
static_assert(sizeof(SceneVertex) == 32, "Metal vertex stride must be 32 bytes");
static_assert(offsetof(SceneVertex, uv) == 16, "Metal texture coordinate offset changed");

struct SceneSprite {
    std::size_t unit_index;
    SpriteResource resource;
    AtlasDescriptor descriptor;
};

// Actual first-campaign resources and native geometry. Camera and interaction
// policy belong to the viewer. This does not advance past the bootstrap stop.
class FirstMissionScene {
public:
    FirstMissionScene(const Archive& archive, const Bytes& terrain_tables);
    WorldBootstrap world;
    TerrainMesh terrain;
    std::map<std::uint32_t, RgbaImage> textures;
    std::vector<SceneSprite> sprites;
};

std::vector<SceneVertex> terrain_vertices(const TerrainMesh&);
std::vector<SceneVertex> sprite_vertices(const AtlasDescriptor&, std::size_t frame);

} // namespace g1
