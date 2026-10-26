#pragma once

#import <Metal/Metal.h>

#include "g1/Scene.hpp"
#include <memory>

namespace g1 {
using Matrix4 = std::array<float, 16>; // Column-major, Metal clip depth 0..1.

struct MetalMesh {
    id<MTLBuffer> vertices;
    NSUInteger count{};
};

struct MetalDraw {
    std::shared_ptr<MetalMesh> mesh;
    id<MTLTexture> texture;
    Matrix4 matrix;
    std::array<float, 4> tint{{1, 1, 1, 1}};
    bool depth_write{true};
    std::array<float,2> uv_offset{};
};

class MetalRenderer {
public:
    explicit MetalRenderer(id<MTLDevice> device);
    std::shared_ptr<MetalMesh> mesh(const std::vector<SceneVertex>&);
    id<MTLTexture> texture(const RgbaImage&);
    void encode(id<MTLCommandBuffer>, MTLRenderPassDescriptor*,
                const std::vector<MetalDraw>&);
private:
    id<MTLDevice> device_;
    id<MTLRenderPipelineState> pipeline_;
    id<MTLSamplerState> sampler_;
    id<MTLDepthStencilState> depth_write_, depth_read_;
};

Matrix4 identity_matrix() noexcept;
Matrix4 multiply_matrix(const Matrix4&, const Matrix4&) noexcept;
} // namespace g1
