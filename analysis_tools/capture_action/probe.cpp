// Development-only structured stdin probe; no original executable is linked.
#include "g1/CaptureAction.hpp"
#include <iostream>
#include <stdexcept>

int number() { int value; if (!(std::cin >> value)) throw std::runtime_error("Short probe input"); return value; }
void output(const g1::CaptureNetwork& n) {
    std::cout << "{\"counters\":[" << n.counters_68[0] << ',' << n.counters_68[1] << "],\"owners\":[";
    for (std::size_t s=0;s<n.sites.size();++s) {
        if(s)std::cout<<',';
        std::cout<<int(n.sites[s].state);
    }
    std::cout<<"],\"items\":[";
    for(std::size_t s=0;s<n.sites.size();++s){
        if(s)std::cout<<',';
        std::cout<<'[';
        for(std::size_t g=0;g<n.sites[s].item_states.size();++g){
            if(g)std::cout<<',';
            std::cout<<'[';
            for(std::size_t i=0;i<n.sites[s].item_states[g].size();++i){if(i)std::cout<<',';std::cout<<int(n.sites[s].item_states[g][i]);}
            std::cout<<']';
        }
        std::cout<<']';
    }
    std::cout<<"],\"links\":[";
    for(std::size_t s=0;s<n.item_links.size();++s){
        if(s)std::cout<<',';
        std::cout<<'[';
        for(std::size_t g=0;g<n.item_links[s].size();++g){
            if(g)std::cout<<',';
            std::cout<<'[';
            for(std::size_t i=0;i<n.item_links[s][g].size();++i){if(i)std::cout<<',';std::cout<<int(n.item_links[s][g][i]);}
            std::cout<<']';
        }
        std::cout<<']';
    }
    std::cout<<"]}";
}
int main(){try{
    const int count=number();std::cout<<'[';
    for(int c=0;c<count;++c){
        const int mode=number();
        std::array<std::int8_t,2> factions{{static_cast<std::int8_t>(number()),static_cast<std::int8_t>(number())}};
        const bool counters=number()!=0,links=number()!=0;
        const int sites=number();g1::CaptureNetwork n;
        n.counters_68={{number(),number()}};
        std::vector<g1::WorldSite> coordinates;
        for(int s=0;s<sites;++s){
            g1::MissionSiteState state;state.state=static_cast<std::int8_t>(number());
            g1::WorldSite coordinate;coordinate.position={static_cast<std::uint8_t>(number()),static_cast<std::uint8_t>(number())};
            const int groups=number();std::vector<std::vector<std::uint8_t>> slinks;
            for(int g=0;g<groups;++g){
                const int items=number();std::vector<std::int8_t> owners;std::vector<std::uint8_t> glinks;std::vector<g1::WorldCoordinate> positions;
                for(int i=0;i<items;++i){owners.push_back(static_cast<std::int8_t>(number()));glinks.push_back(static_cast<std::uint8_t>(number()));positions.push_back({static_cast<std::uint8_t>(number()),static_cast<std::uint8_t>(number())});}
                state.item_states.push_back(owners);slinks.push_back(glinks);coordinate.coordinate_groups.push_back(positions);
            }
            n.sites.push_back(state);n.item_links.push_back(slinks);coordinates.push_back(coordinate);
        }
        if(c)std::cout<<',';
        if(mode==0){g1::refresh_capture_network(n,factions,counters,links);output(n);}
        else if(mode==1){
            g1::WorldCoordinate point{static_cast<std::uint8_t>(number()),static_cast<std::uint8_t>(number())};
            auto target=g1::choose_capture_target(coordinates,point);
            if(!target)std::cout<<"null";
            else std::cout<<'['<<int(target->kind)<<','<<target->site<<','<<target->group<<','<<target->item<<']';
        }else if(mode==2){
            g1::CaptureActor actor;actor.owner=static_cast<std::uint8_t>(number());actor.position={static_cast<std::uint8_t>(number()),static_cast<std::uint8_t>(number())};actor.form_field10=1;
            const auto result=g1::perform_capture(coordinates,n,actor,factions,{{0,1}});
            if(result.status!=g1::CaptureStatus::captured)throw std::runtime_error("Expected native capture");
            std::cout<<"{\"network\":";output(n);std::cout<<",\"flag2c\":"<<int(actor.flag_2c)<<'}';
        }else throw std::runtime_error("Unknown probe mode");
    }
    std::cout<<"]\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
