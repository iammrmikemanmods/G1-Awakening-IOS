#include "g1/M3GCamera.hpp"
#include "m3g_camera_fixture.hpp"
#include "m3g_animation_fixture.hpp"

#include <cmath>
#include <functional>
#include <iostream>
#include <limits>

namespace {
std::size_t comparisons=0,contracts=0;
void check(bool v,const char* text) { ++contracts;if(!v)throw std::runtime_error(text); }
void rejects(const std::function<void()>& action,const char* text) {
    bool failed=false;try { action(); }catch(const g1::FormatError&) { failed=true; }check(failed,text);
}
std::uint32_t bits(float value) { std::uint32_t result;std::memcpy(&result,&value,4);return result; }
g1::Bytes camera_file(std::uint8_t type,const std::vector<float>& fields) {
    auto camera=g1_test::node();camera.push_back(type);for(auto v:fields)g1_test::scalar(camera,v);
    auto raw=g1_test::chunk(5,camera);auto world=g1_test::node();
    g1_test::u32(world,1);g1_test::u32(world,2);g1_test::u32(world,2);g1_test::u32(world,0);
    g1_test::append(raw,g1_test::chunk(22,world));return g1_test::file(raw);
}
}

int main() {
    try {
        for(const auto& row:g1_camera_fixture::cases) {
            g1::M3GCameraProjection camera;camera.type=row.type;camera.parameters=row.parameters;
            const auto matrix=g1::m3g_camera_projection_matrix(camera);
            for(std::size_t n=0;n<16;++n) { ++comparisons;if(bits(matrix[n])!=row.matrix_bits[n])throw std::runtime_error("original camera projection bits differ"); }
        }
        const auto decoded=g1::decode_m3g_cameras(camera_file(50,{30,1.5F,2,5000}));
        check(decoded.size()==1 && decoded.at(2).type==50 && decoded.at(2).parameters==std::array<float,4>{{30,1.5F,2,5000}},"serialized camera parameters");
        const auto generic=g1::decode_m3g_cameras(camera_file(48,{1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16}));
        check(generic.at(2).generic==g1::M3GMatrix{{1,5,9,13,2,6,10,14,3,7,11,15,4,8,12,16}},"generic projection transpose");
        auto camera=decoded.at(2);
        const g1::M3GMatrix identity{{1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1}};
        const auto metal=g1::m3g_camera_metal_view_projection(camera,identity);
        const auto depth=[&](float z) { return (metal[10]*z+metal[14])/(metal[11]*z+metal[15]); };
        check(std::abs(depth(-2))<0.000001F && std::abs(depth(-5000)-1)<0.000001F,"Metal depth mapping");
        const g1::M3GMatrix posed{{0,2,0,0,-3,0,0,0,0,0,4,0,5,-6,7,1}};
        const auto inverse=g1::m3g_camera_view_matrix(posed);
        const auto unit=g1::m3g_multiply(inverse,posed);
        for(std::size_t n=0;n<16;++n)check(std::abs(unit[n]-identity[n])<0.000001F,"affine camera inverse");
        auto bad=posed;bad[0]=bad[1]=bad[2]=0;
        rejects([&]{(void)g1::m3g_camera_view_matrix(bad);},"singular camera accepted");
        bad={{2895626,6180765,9076391,0,2933305,5289181,8222486,0,6895124,4568742,11463866,0,0,0,0,1}};
        rejects([&]{(void)g1::m3g_camera_view_matrix(bad);},"exactly dependent float32 rows survived cofactor cancellation");
        bad=posed;bad[3]=1;rejects([&]{(void)g1::m3g_camera_view_matrix(bad);},"nonaffine camera accepted");
        bad=posed;bad[0]=std::numeric_limits<float>::infinity();rejects([&]{(void)g1::m3g_camera_view_matrix(bad);},"nonfinite camera accepted");
        camera.parameters[3]=camera.parameters[2];rejects([&]{(void)g1::m3g_camera_projection_matrix(camera);},"zero-volume projection accepted");
        camera=decoded.at(2);camera.parameters[0]=180;rejects([&]{(void)g1::m3g_camera_projection_matrix(camera);},"invalid perspective fovy accepted");
        camera=decoded.at(2);camera.parameters[1]=0;rejects([&]{(void)g1::m3g_camera_projection_matrix(camera);},"zero aspect accepted");
        camera=decoded.at(2);camera.parameters[2]=-1;rejects([&]{(void)g1::m3g_camera_projection_matrix(camera);},"negative perspective near accepted");
        rejects([&]{(void)g1::decode_m3g_cameras(camera_file(50,{30,1.5F,2}));},"truncated camera body accepted");
        std::cout<<"{\"original_cases\":"<<g1_camera_fixture::cases.size()<<",\"projection_comparisons\":"<<comparisons
                 <<",\"native_contracts\":"<<contracts<<",\"passed\":true}\n";
        return 0;
    } catch(const std::exception& error) { std::cerr<<"FAIL: "<<error.what()<<'\n';return 1; }
}
