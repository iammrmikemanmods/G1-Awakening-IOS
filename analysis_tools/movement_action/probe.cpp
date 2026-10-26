// Development-only native reference bridge; no original executable input.
#include "g1/MovementAction.hpp"
#include <iostream>
#include <stdexcept>
#include <string>

void state(const g1::MovementAction& action) {
    const auto& s=action.state();
    std::cout << '[' << int(s.tile_x) << ',' << int(s.tile_y) << ',' << s.offset_x << ','
      << s.offset_y << ',' << int(s.facing) << ',' << int(s.spent_budget) << ','
      << int(action.pending_cost()) << ',' << int(action.route_index()) << ','
      << (action.moving()?1:0) << ',' << s.timer_ms << ',' << int(s.flag_38) << ','
      << int(s.anchor_x) << ',' << int(s.anchor_y) << ',' << int(s.anchor_facing) << ','
      << int(s.flag_2c) << ',' << int(s.flag_2d) << ',' << int(s.flag_2f) << ','
      << int(s.flag_39) << ',' << int(s.flag_3a) << ']';
}

int main() {
    try {
        std::size_t count; std::cin>>count;
        std::cout << '[';
        for(std::size_t c=0;c<count;++c) {
            std::string name;
            int w,h,ox,oy,dx,dy,type,owner,budget,spent,form,field2,timer,facing,aux,f2c,f2f,f39;
            std::size_t ticks;
            std::cin>>name>>w>>h>>ox>>oy>>dx>>dy>>type>>owner>>budget>>spent>>form>>field2
                    >>timer>>facing>>aux>>f2c>>f2f>>f39>>ticks;
            g1::MovementRange range;
            range.width=std::uint16_t(w);range.height=std::uint16_t(h);
            range.remaining.resize(std::size_t(w)*h);
            for(auto& v:range.remaining)std::cin>>v;
            std::vector<std::uint32_t> deltas(ticks);
            for(auto& d:deltas)std::cin>>d;
            if(!std::cin)throw std::runtime_error("malformed probe input");
            const auto route=g1::choose_movement_route(range,
                {std::uint8_t(ox),std::uint8_t(oy)},{std::uint8_t(dx),std::uint8_t(dy)});
            if(c)std::cout<<',';
            std::cout<<"{\"name\":\""<<name<<"\",\"status\":"<<int(route.status)<<",\"route\":[";
            for(std::size_t i=0;i<route.steps.size();++i) {
                if(i)std::cout<<',';
                std::cout<<'['<<int(route.steps[i].x)<<','<<int(route.steps[i].y)<<']';
            }
            std::cout<<"],\"states\":[";
            if(route.status==g1::MovementRouteStatus::ready) {
                g1::MovementUnitState s;
                s.tile_x=std::uint8_t(ox);s.tile_y=std::uint8_t(oy);
                s.anchor_x=s.tile_x;s.anchor_y=s.tile_y;s.anchor_facing=std::uint8_t(facing);
                s.spent_budget=std::uint8_t(spent);s.form=std::uint8_t(form);s.timer_ms=timer;
                s.facing=std::uint8_t(facing);s.flag_38=std::uint8_t(aux);
                s.flag_2c=std::uint8_t(f2c);s.flag_2f=std::uint8_t(f2f);s.flag_39=std::uint8_t(f39);
                g1::MovementProfile p{std::uint8_t(type),std::uint8_t(owner),std::uint8_t(budget),
                                      std::uint8_t(spent),0};
                g1::MovementAction action(s,p,range,route,std::int8_t(field2));
                state(action);
                for(auto d:deltas) { action.advance_tick(d);std::cout<<',';state(action); }
                std::cout<<"],\"undo\":";
                if(!action.moving()) {
                    action.undo_ordinary();state(action);
                } else std::cout<<"null";
            } else std::cout<<"],\"undo\":null";
            std::cout<<'}';
        }
        std::cout<<"]\n";
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
