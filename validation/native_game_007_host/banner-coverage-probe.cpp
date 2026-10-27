#include "g1/BitmapFont.hpp"
#include "g1/Text.hpp"
#include "g1/World.hpp"
#include <algorithm>
#include <iostream>
#include <set>

int main(int argc,char** argv) {
    if(argc!=2)return 2;
    const g1::Archive archive(g1::read_file(argv[1]));
    const auto text=g1::load_text_table(archive);
    const auto large=g1::load_bitmap_font_assets(archive,0);
    const auto small=g1::load_bitmap_font_assets(archive,2);
    for(const auto* face:{&large,&small}) {
        const auto metrics=face->descriptor.metrics();
        std::cout<<"slot="<<face->font_slot<<" height="<<metrics.height<<" line="<<metrics.line_height
                 <<" adjust="<<metrics.draw_y_adjustment<<" glyphs="<<face->descriptor.glyphs().size()<<'\n';
        for(const auto& glyph:face->descriptor.glyphs())
            if(glyph.width==0 || glyph.height==0) {
                std::cerr<<"zero-sized glyph "<<static_cast<unsigned>(glyph.character)<<'\n';return 1;
            }
    }
    std::size_t small_selected=0,large_selected=0;
    for(std::uint8_t type=0;type<23;++type) {
        const auto resource=g1::unit_definition_resource(type);
        const auto records=archive.find(resource,0xf4e02223U);
        if(records.size()!=1)return 1;
        const auto unit=g1::decode_unit_definition(archive.read(records.front()),type,resource);
        const auto name=text.at(g1::script_text_id(g1::unit_text_index(unit.raw_text_indices[0])));
        const auto banner=name+" "+text.at(503);
        const auto characters=g1::bitmap_font_utf8(banner);
        const auto supports=[&](const g1::BitmapFontAssets& face) {
            return std::all_of(characters.begin(),characters.end(),[&](char32_t c) {
                return c!=U'\n' && c!=U'\r' && face.descriptor.contains(c);
            });
        };
        const auto* face=supports(large) ? &large : supports(small) ? &small : nullptr;
        if(!face){std::cerr<<"unsupported banner for type="<<unsigned(type)<<'\n';return 1;}
        if(face==&small)++small_selected;else ++large_selected;
        const auto measured=face->descriptor.measure(characters);
        int min_x=0,min_y=0,max_x=0,max_y=0;
        for(const auto& draw:face->descriptor.layout(characters)) {
            min_x=std::min(min_x,draw.x);min_y=std::min(min_y,draw.y);
            max_x=std::max(max_x,draw.x+draw.width);max_y=std::max(max_y,draw.y+draw.height);
        }
        std::cout<<"type="<<unsigned(type)<<" slot="<<face->font_slot<<" measured="<<measured.width
                 <<" bounds="<<min_x<<','<<min_y<<':'<<max_x<<','<<max_y<<" banner="<<banner<<'\n';
    }
    std::cout<<"All 23 primary-name + actual text503 banners supported: slot0="<<large_selected
             <<", slot2="<<small_selected<<", fallback=0\n";
}
