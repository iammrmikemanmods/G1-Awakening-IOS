#include "g1/TransformAction.hpp"
#include <iostream>
#include <stdexcept>
int number(){int n;if(!(std::cin>>n))throw std::runtime_error("Short input");return n;}
int main(){try{
    const int count=number();std::cout<<'[';
    for(int c=0;c<count;++c){
        g1::UnitDefinition d;d.type=11;d.scalar_fields[2]=static_cast<std::uint8_t>(number());
        g1::MovementUnitState u;
        u.form=static_cast<std::uint8_t>(number());u.active=number()!=0;
        u.flag_2c=static_cast<std::uint8_t>(number());u.flag_2d=static_cast<std::uint8_t>(number());
        const auto pending=static_cast<std::uint8_t>(number());u.flag_2f=static_cast<std::uint8_t>(number());
        u.facing=static_cast<std::uint8_t>(number());u.spent_budget=static_cast<std::uint8_t>(number());
        const auto level=static_cast<std::uint8_t>(number());const bool record=number()!=0;
        const bool audio=number()!=0;const int terrain0=number(),terrain2=number();
        for(int f=0;f<2;++f){g1::Bytes bytes;for(int i=0;i<14;++i)bytes.push_back(static_cast<std::uint8_t>(number()));d.forms.push_back(bytes);}
        const bool eligible=g1::transform_eligibility(u,d,terrain0,terrain2)==g1::TransformEligibility::allowed;
        const auto r=g1::transform_unit(u,d,level,pending,record,audio);
        if(c)std::cout<<',';
        std::cout<<"{\"eligible\":"<<(eligible?"true":"false")<<",\"unit\":["<<int(r.unit.form)<<','<<int(r.unit.flag_2c)<<','<<int(r.unit.flag_2d)<<','<<int(r.animation_pending_2e)<<','<<int(r.unit.flag_2f)<<','<<int(r.unit.facing)<<','<<int(r.unit.spent_budget)<<"],\"stats\":["<<r.stats.attack_low<<','<<r.stats.attack_high<<','<<r.stats.defense<<"],\"audio\":";
        if(r.audio_event_in_group5)std::cout<<int(*r.audio_event_in_group5);else std::cout<<"null";
        std::cout<<'}';
    }
    std::cout<<"]\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
