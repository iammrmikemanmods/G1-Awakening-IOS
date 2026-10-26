#include "g1/Scene.hpp"

namespace g1 {
namespace {
Bytes read_resource(const Archive& archive, std::uint32_t id, std::uint32_t key) {
    const auto found = archive.find(id, key);
    if (found.size() != 1) throw FormatError("scene resource is missing or ambiguous");
    return archive.read(found.front());
}

void texture(const Archive& archive, std::map<std::uint32_t, RgbaImage>& textures,
             std::uint32_t id, std::uint32_t key, std::uint32_t width, std::uint32_t height) {
    if (textures.count(id) != 0) return;
    auto image = decode_png(read_resource(archive, id, key));
    if (image.width != width || image.height != height)
        throw FormatError("scene texture dimensions differ from the recovered atlas");
    textures.emplace(id, std::move(image));
}
} // namespace

FirstMissionScene::FirstMissionScene(const Archive& archive, const Bytes& tables)
    : world(bootstrap_first_campaign(archive)),
      terrain(build_terrain_mesh(world.grid, decode_terrain_tables(tables), world.style)) {
    constexpr std::uint32_t key = 0xf4e02223U;
    texture(archive, textures, terrain.atlas_resource_id, key, 512, 256);
    for (std::size_t i = 0; i < world.units.size(); ++i) {
        const auto mapping = sprite_resource_for_type(world.units[i].type);
        if (!mapping) throw FormatError("initial unit has no recovered sprite mapping");
        texture(archive, textures, mapping->image_id, mapping->resource_key, 512, 512);
        sprites.push_back({i, *mapping, AtlasDescriptor(
            read_resource(archive, mapping->descriptor_id, mapping->resource_key))});
    }
}

std::vector<SceneVertex> terrain_vertices(const TerrainMesh& mesh) {
    std::vector<SceneVertex> result;
    result.reserve(mesh.quads.size() * 6);
    for (const auto& quad : mesh.quads) {
        for (const auto index : sprite_triangle_indices) {
            const auto& p = quad.positions[index];
            result.push_back({{p[0] * mesh.position_scale, p[1] * mesh.position_scale,
                               p[2] * mesh.position_scale, 1.0F}, quad.normalized_uv[index], {}});
        }
    }
    return result;
}

std::vector<SceneVertex> sprite_vertices(const AtlasDescriptor& descriptor, std::size_t frame) {
    const auto quads = make_sprite_geometry(descriptor, frame);
    std::vector<SceneVertex> result;
    result.reserve(quads.size() * 6);
    for (const auto& quad : quads) {
        for (const auto index : sprite_triangle_indices) {
            const auto& v = quad.vertices[index];
            result.push_back({{v.position[0], v.position[1], v.position[2], 1.0F}, v.uv, {}});
        }
    }
    return result;
}
} // namespace g1
