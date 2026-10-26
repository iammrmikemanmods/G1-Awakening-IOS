// Development-only native bridge for the original arrival-facing slice.
#include "g1/MovementArrival.hpp"
#include <iostream>
#include <stdexcept>

g1::ArrivalUnit read_unit() {
    int type,owner,x,y,facing,active;
    std::cin>>type>>owner>>x>>y>>facing>>active;
    return {std::uint8_t(type),std::uint8_t(owner),std::uint8_t(x),std::uint8_t(y),
            std::uint8_t(facing),active!=0};
}
int main() {
    try {
        std::size_t cases;std::cin>>cases;std::cout<<'[';
        for(std::size_t c=0;c<cases;++c) {
            const auto actor=read_unit();int low,high,field;
            std::size_t count;std::cin>>low>>high>>field>>count;
            std::vector<g1::ArrivalUnit> units;
            for(std::size_t i=0;i<count;++i)units.push_back(read_unit());
            if(!std::cin)throw std::runtime_error("malformed arrival probe input");
            const auto result=g1::choose_movement_arrival_facing(actor,units,
                std::uint8_t(low),std::uint8_t(high),std::int8_t(field));
            if(c)std::cout<<',';
            std::cout<<"{\"writes_facing\":"<<(result.writes_facing?"true":"false")
                     <<",\"facing\":"<<int(result.facing)<<",\"targets\":";
            if(result.target_types) {
                std::cout<<'[';
                for(std::size_t i=0;i<result.target_types->size();++i) {
                    if(i)std::cout<<',';
                    std::cout<<int((*result.target_types)[i]);
                }
                std::cout<<']';
            }else std::cout<<"null";
            std::cout<<",\"nearest\":";
            if(result.nearest_type)std::cout<<int(*result.nearest_type);else std::cout<<"null";
            std::cout<<'}';
        }
        std::cout<<"]\n";
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
