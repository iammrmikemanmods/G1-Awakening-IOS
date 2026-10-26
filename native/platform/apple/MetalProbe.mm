#include "MetalRenderer.hpp"

#include <fstream>
#include <iostream>

namespace {
std::vector<g1::SceneVertex> quad(float half, float depth) {
    const std::array<g1::SceneVertex, 4> vertices{{
        {{-half, half,depth,1},{0,0},{}}, {{-half,-half,depth,1},{0,1},{}},
        {{ half, half,depth,1},{1,0},{}}, {{ half,-half,depth,1},{1,1},{}}}};
    std::vector<g1::SceneVertex> result;
    for (const auto index : g1::sprite_triangle_indices) result.push_back(vertices[index]);
    return result;
}

g1::RgbaImage render(id<MTLDevice> device, g1::MetalRenderer& renderer,
                     const std::vector<g1::MetalDraw>& draws) {
    MTLTextureDescriptor* colorDesc = [MTLTextureDescriptor
        texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm
        width:64 height:64 mipmapped:NO];
    colorDesc.storageMode = MTLStorageModeShared;
    colorDesc.usage = MTLTextureUsageRenderTarget;
    id<MTLTexture> color = [device newTextureWithDescriptor:colorDesc];
    MTLTextureDescriptor* depthDesc = [MTLTextureDescriptor
        texture2DDescriptorWithPixelFormat:MTLPixelFormatDepth32Float
        width:64 height:64 mipmapped:NO];
    depthDesc.storageMode = MTLStorageModePrivate;
    depthDesc.usage = MTLTextureUsageRenderTarget;
    id<MTLTexture> depth = [device newTextureWithDescriptor:depthDesc];
    if (!color || !depth) throw std::runtime_error("offscreen attachment allocation failed");
    MTLRenderPassDescriptor* pass = [MTLRenderPassDescriptor new];
    pass.colorAttachments[0].texture = color;
    pass.colorAttachments[0].loadAction = MTLLoadActionClear;
    pass.colorAttachments[0].storeAction = MTLStoreActionStore;
    pass.colorAttachments[0].clearColor = MTLClearColorMake(0, 0, 0, 1);
    pass.depthAttachment.texture = depth;
    pass.depthAttachment.loadAction = MTLLoadActionClear;
    pass.depthAttachment.storeAction = MTLStoreActionDontCare;
    pass.depthAttachment.clearDepth = 1.0;
    id<MTLCommandQueue> queue = [device newCommandQueue];
    id<MTLCommandBuffer> command = [queue commandBuffer];
    renderer.encode(command, pass, draws);
    [command commit];
    [command waitUntilCompleted];
    if (command.status != MTLCommandBufferStatusCompleted)
        throw std::runtime_error(command.error.localizedDescription.UTF8String ?: "Metal command failed");
    g1::RgbaImage image{64,64,g1::Bytes(64 * 64 * 4)};
    [color getBytes:image.pixels.data() bytesPerRow:64 * 4
        fromRegion:MTLRegionMake2D(0, 0, 64, 64) mipmapLevel:0];
    for (std::size_t i = 0; i < image.pixels.size(); i += 4)
        std::swap(image.pixels[i], image.pixels[i + 2]);
    return image;
}

void pixel(const g1::RgbaImage& image, unsigned x, unsigned y,
           std::array<int, 4> expected, const char* check) {
    const auto offset = (std::size_t(y) * image.width + x) * 4;
    for (std::size_t c = 0; c < 4; ++c)
        if (std::abs(int(image.pixels[offset + c]) - expected[c]) > 2)
            throw std::runtime_error(std::string(check) + " channel " + std::to_string(c) +
                " expected " + std::to_string(expected[c]) + " observed " +
                std::to_string(image.pixels[offset + c]));
}
} // namespace

int main(int argc, char** argv) {
    @autoreleasepool {
        try {
            id<MTLDevice> device = MTLCreateSystemDefaultDevice();
            if (!device) {
                std::cout << "{\"metal_device_available\":false,\"pixel_test\":\"not run\"}\n";
                return 77; // CTest records a skip, never a graphics pass.
            }
            g1::MetalRenderer renderer(device);
            const auto full = renderer.mesh(quad(1, 0.5F));
            // Encode/decode through the same native PNG path used by game
            // assets. Known corner colors establish UV/row/alpha behavior.
            const g1::RgbaImage corners{2,2,{255,0,0,255, 0,255,0,128,
                                             0,0,255,0, 23,47,91,63}};
            id<MTLTexture> texture = renderer.texture(g1::decode_png(g1::encode_png(corners)));
            const auto matrix = g1::identity_matrix();
            const auto image = render(device, renderer, {{full,texture,matrix,{{1,1,1,1}},true}});
            pixel(image,8,8,{{255,0,0,255}},"top-left/row orientation");
            pixel(image,55,8,{{0,128,0,255}},"straight-alpha blending");
            pixel(image,8,55,{{0,0,0,255}},"transparent-fragment discard");
            pixel(image,55,55,{{6,12,22,255}},"RGBA channels and alpha");
            id<MTLTexture> white = renderer.texture({1,1,{255,255,255,255}});
            const auto near = renderer.mesh(quad(0.5F,0.2F));
            const auto far = renderer.mesh(quad(1,0.8F));
            const auto depth = render(device,renderer,{
                {full,white,matrix,{{1,0,0,1}},true},
                {near,white,matrix,{{0,1,0,1}},true},
                {far,white,matrix,{{0,0,1,1}},true}});
            pixel(depth,32,32,{{0,255,0,255}},"front fragment depth");
            pixel(depth,8,8,{{255,0,0,255}},"behind fragment rejection");
            if (argc == 2) {
                const auto png = g1::encode_png(image);
                std::ofstream out(argv[1], std::ios::binary);
                out.write(reinterpret_cast<const char*>(png.data()), png.size());
                if (!out) throw std::runtime_error("cannot write probe PNG");
            }
            std::cout << "{\"metal_device_available\":true,\"device\":\""
                      << device.name.UTF8String << "\",\"pixel_checks\":6,"
                      << "\"pixel_channels_compared\":24,\"result\":\"passed\","
                      << "\"original_game_data_used\":false,\"iphone_execution\":false}\n";
            return 0;
        } catch (const std::exception& error) {
            std::cerr << "ERROR: " << error.what() << '\n';
            return 1;
        }
    }
}
