#include "g1/TerrainDecorations.hpp"
#include "g1/Combat.hpp"

#include <iostream>
#include <string>

namespace {
std::uint32_t number() {
    std::uint32_t n{};
    if (!(std::cin >> n)) throw g1::FormatError("short decoration probe input");
    return n;
}
g1::Bytes bytes() {
    const auto n=number();
    if (n>65535) throw g1::FormatError("decoration probe byte vector is too large");
    g1::Bytes out;out.reserve(n);
    for (std::uint32_t i=0;i<n;++i) {
        const auto v=number();
        if (v>255) throw g1::FormatError("decoration probe byte is out of range");
        out.push_back(static_cast<std::uint8_t>(v));
    }
    return out;
}
template<class R> void numbers(const R& values) {
    std::cout << '[';
    bool first=true;
    for (const auto& v:values) {if(!first)std::cout<<',';first=false;std::cout<<+v;}
    std::cout << ']';
}
void snapshot(const g1::TerrainDecorationLayout& layout,const g1::TerrainDecorationState& state,
              const g1::TerrainGrid& grid,const g1::TerrainTables& tables,const g1::GameRandom& random) {
    std::cout << "{\"candidate_records\":";numbers(state.candidate_records);
    std::vector<std::int32_t> offsets;
    std::vector<std::uint8_t> phases;
    for(const auto& slot:state.slots){offsets.push_back(slot.candidate_byte_offset);phases.push_back(slot.phase);}
    std::cout << ",\"slot_offsets\":";numbers(offsets);
    std::cout << ",\"slot_phases\":";numbers(phases);
    const auto quads=g1::terrain_decoration_quads(layout,state,grid,tables);
    std::cout << ",\"positions\":[";
    for(std::size_t i=0;i<quads.size();++i){
        if(i)std::cout<<',';
        std::vector<std::int16_t> flat;
        for(const auto& row:quads[i].positions)flat.insert(flat.end(),row.begin(),row.end());
        numbers(flat);
    }
    std::cout << "],\"uv\":[";
    for(std::size_t i=0;i<quads.size();++i){
        if(i)std::cout<<',';
        std::vector<std::int16_t> flat;
        for(const auto& row:quads[i].quantized_uv)flat.insert(flat.end(),row.begin(),row.end());
        numbers(flat);
    }
    std::cout << "],\"accumulated_ms\":" << state.animation.accumulated_ms
              << ",\"phase\":" << +state.animation.phase
              << ",\"random_index\":" << random.state().index
              << ",\"random_draws\":" << random.state().draws << ",\"random_words\":";
    numbers(random.state().words);
    std::cout << '}';
}
}

int main(){
    try{
        std::string magic;std::cin>>magic;
        if(magic!="G1_TERRAIN_DECORATION_INPUT_V1")throw g1::FormatError("wrong decoration probe magic");
        g1::GameRandom random(number());
        const auto grid=g1::decode_terrain_grid(bytes());
        const auto tables=g1::decode_terrain_tables(bytes());
        const auto config=g1::decode_terrain_animation_config(bytes());
        const auto layout=g1::build_terrain_decoration_layout(grid,tables,config);
        auto state=g1::create_terrain_decorations(layout,random);
        const auto count=number();
        if(count>4096)throw g1::FormatError("decoration probe step bound exceeded");
        std::cout << "{\"layout\":{\"candidate_capacity\":" << layout.initial_candidate_records.size()/3
                  << ",\"registered_candidates\":" << layout.registered_candidates
                  << ",\"slot_count\":" << state.slots.size()
                  << ",\"total_mesh_quads\":" << layout.mesh_quad_capacity << "},\"snapshots\":[";
        snapshot(layout,state,grid,tables,random);
        for(std::uint32_t i=0;i<count;++i){
            g1::advance_terrain_decorations(layout,state,number(),random);
            std::cout << ',';snapshot(layout,state,grid,tables,random);
        }
        if(std::cin>>magic)throw g1::FormatError("trailing decoration probe input");
        std::cout << "]}\n";
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
