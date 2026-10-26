#include "g1/CampaignController.hpp"

#include <filesystem>
#include <fstream>
#include <functional>
#include <iostream>
#include <map>
#include <type_traits>
#include <unistd.h>

namespace {
static_assert(!std::is_copy_constructible<g1::CampaignController>::value &&
              !std::is_move_constructible<g1::CampaignController>::value,
              "a campaign transaction cannot duplicate its token owner");
std::size_t checks{};
void check(bool value,const char* message) {
    ++checks;if(!value)throw std::runtime_error(message);
}
void rejects(const std::function<void()>& fn,const char* message) {
    try{fn();}catch(const g1::FormatError&){++checks;return;}
    throw std::runtime_error(message);
}
bool same_random(const g1::GameRandom::State& a,const g1::GameRandom::State& b) {
    return a.index==b.index && a.draws==b.draws && a.words==b.words;
}
void put32(g1::Bytes& bytes,std::size_t at,std::size_t value) {
    for(std::size_t i=0;i<4;++i)bytes.at(at+i)=static_cast<std::uint8_t>(value>>(8U*i));
}
g1::Bytes script(std::initializer_list<std::vector<std::uint16_t>> commands) {
    g1::Bytes result{1,static_cast<std::uint8_t>(commands.size())};
    for(const auto& command:commands)for(const auto word:command) {
        result.push_back(static_cast<std::uint8_t>(word>>8U));result.push_back(static_cast<std::uint8_t>(word));
    }
    return result;
}
g1::Archive archive(bool include_next=true,bool fail_after_random=false) {
    // Constructed inputs only; no proprietary resource bytes are embedded.
    std::map<std::uint32_t,g1::Bytes> payloads;
    for(std::uint8_t type=0;type<23;++type) {
        g1::Bytes bytes{0,0,0,0,0,static_cast<std::uint8_t>(type==19U?1:0),7,1,0,0,0,2};
        for(int form=0;form<2;++form) {
            bytes.push_back(14);const auto at=bytes.size();bytes.resize(at+14,0);
            bytes[at]=4;bytes[at+1]=1;bytes[at+2]=1;bytes[at+3]=10;bytes[at+4]=12;bytes[at+5]=3;
        }
        payloads[g1::unit_definition_resource(type)]=std::move(bytes);
    }
    payloads[306]={4,3,1,0,0,3,3,0,0,3,1,0,0,3,99,0,0};
    payloads[268]=g1::Bytes(66,0);payloads[268][0]=8;payloads[268][1]=8;
    payloads[282]=g1::Bytes(33,0);payloads[282][0]=1;
    if(include_next)payloads[326]=fail_after_random ?
        script({{0},{16,208},{9,0,0},{6,65535,1,1,0,0},{9,0,0},{4,1,1,1}}) :
        script({{0},{16,208},{9,0,0},{6,65535,1,1,0,0},{4,1,1,1},{12,2,239,65534}});
    const auto count=payloads.size(),members=32U+count*8U,body=members+(count+1U)*8U;
    g1::Bytes bytes(body,0);
    put32(bytes,0,0x42494746U);put32(bytes,4,0x00800001U);put32(bytes,8,32);put32(bytes,12,count);
    put32(bytes,16,members);put32(bytes,20,count);put32(bytes,24,body);
    std::size_t index{};
    for(const auto& item:payloads) {
        const auto at=32U+index*8U;put32(bytes,at,item.first);bytes[at+4]=1;
        bytes[at+6]=static_cast<std::uint8_t>(index);bytes[at+7]=static_cast<std::uint8_t>(index>>8U);
        put32(bytes,members+index*8U,0xf4e02223U);put32(bytes,members+index*8U+4U,bytes.size());
        const auto payload=bytes.size();bytes.resize(payload+4);put32(bytes,payload,4);
        bytes.insert(bytes.end(),item.second.begin(),item.second.end());++index;
    }
    put32(bytes,members+count*8U+4U,bytes.size());put32(bytes,28,bytes.size()-body);
    return g1::Archive(std::move(bytes));
}
g1::CampaignBootstrap fixture(const g1::Archive& archive,const g1::CampaignContext& context,
                              std::uint16_t next=1,bool human_active=true,std::uint8_t human_type=11) {
    g1::CampaignBootstrap result;auto& world=result.world;
    world.mission_resource_id=g1::mission_resource_for_campaign(context.group,context.mission_index);
    world.grid_resource_id=268;world.lookup_resource_id=282;world.player_factions=context.player_factions;
    world.grid={8,8,g1::Bytes(64,0)};world.terrain_rules={{{{1,0,0}}}};
    for(std::uint8_t type=0;type<23;++type) {
        const auto id=g1::unit_definition_resource(type);
        world.unit_definitions.push_back(g1::decode_unit_definition(archive.read(archive.find(id,0xf4e02223U).at(0)),type,id));
    }
    world.units={{human_type,0,0,0,1,1,0,human_active,0,{}},{19,1,1,0,6,6,0,true,0,{}}};
    world.stop=g1::BootstrapStop::execution_required;
    world.commands={{0,2,4,10,{next}}};
    for(auto& unit:world.units) {
        auto activation=g1::activate_unit(world.unit_definitions[unit.type],unit,{unit.x,unit.y},1,0,{},{});
        activation.world.active=unit.active;activation.movement.active=unit.active;activation.combat.active=unit.active;
        result.unit_activations.push_back(activation);
        if(unit.active)world.initialization_effects.push_back({g1::WorldInitializationEffectKind::debit_spawn_funds,
            0,unit.owner,activation.signed_cost,{},1});
    }
    g1::GameRandom random(0x1234567U);for(int i=0;i<7;++i)(void)random.next_word();
    result.random_after=random.state();
    return result;
}
void results_continue(g1::CampaignController& controller) {
    const auto token=controller.state().token;
    controller.report_results_presented(token,256);
    const auto input=controller.update_results(token,16,0);
    check(input.request_handoff && input.remaining_input_edges==0,"valid result Continue did not request handoff");
}
} // namespace

int main() {
    std::filesystem::path directory;
    try {
        const auto data=archive();const g1::CampaignContext campaign;
        g1::GameSession source(data,fixture(data,campaign),campaign);
        check(source.mission().stop==g1::MissionStop::campaign_handoff_required &&
              source.random().state().draws==7,"synthetic actual-session gate/RNG fixture failed");
        auto pattern=(std::filesystem::current_path()/"g1-campaign-test-XXXXXX").string();
        std::vector<char> name(pattern.begin(),pattern.end());name.push_back(0);
        const auto made=mkdtemp(name.data());if(!made)throw std::runtime_error("could not create isolated test directory");
        directory=made;
        const auto save_path=(directory/"initially-missing"/"profile.g1native").string();
        g1::CampaignController controller(save_path);
        const auto before=g1::encode_campaign_profile(controller.profile());
        const auto source_random=source.random().state();
        const auto failed=controller.begin(source);
        const auto token=controller.state().token;
        check(!failed.succeeded && !failed.error.empty() && token!=0 &&
              controller.state().gate==g1::CampaignControllerGate::save_failed &&
              controller.state().save_attempts==1 && !controller.state().profile_persisted &&
              !controller.state().results && !controller.state().handoff &&
              g1::encode_campaign_profile(controller.profile())==before,
              "real filesystem failure unlocked campaign state");
        check(!std::filesystem::exists(save_path),"missing-parent failure unexpectedly created destination");
        rejects([&]{(void)controller.begin(source);},"duplicate begin recreated a save transaction");
        rejects([&]{(void)controller.retry_save(token+1);},"stale save retry token accepted");
        rejects([&]{controller.report_results_presented(token,256);},"failed save permitted result presentation");
        rejects([&]{(void)controller.prepare_next_campaign(token,data);},"failed save permitted campaign loading");
        std::filesystem::create_directory(directory/"initially-missing");
        const auto written=controller.retry_save(token);
        check(written.succeeded && written.error.empty() && controller.state().profile_persisted &&
              controller.state().save_attempts==2 && controller.state().gate==g1::CampaignControllerGate::results &&
              controller.state().results && !controller.state().results->drawn && !controller.state().handoff,
              "real successful retry skipped the undrawn result gate");
        const auto saved_bytes=g1::read_file(save_path,4096);
        const auto loaded=g1::decode_campaign_profile(saved_bytes);
        check(g1::encode_campaign_profile(loaded)==g1::encode_campaign_profile(controller.profile()) &&
              loaded.highest_unlocked[0]==1 && loaded.records[0][0].value_274==source.mission_record().value_274,
              "closed profile reload differs from actual saved update");
        rejects([&]{(void)controller.retry_save(token);},"successful save retried as failure");
        rejects([&]{(void)controller.update_results(token,16,100000);},"undrawn result accepted input/time");
        rejects([&]{controller.report_results_presented(token+1,256);},"stale result draw accepted");
        rejects([&]{controller.report_results_presented(token,0);},"invalid result background geometry accepted");
        controller.report_results_presented(token,256);
        const auto idle=controller.update_results(token,0,1000);
        check(!idle.request_handoff && controller.state().gate==g1::CampaignControllerGate::results &&
              idle.background_offset_q16==1024000,"time alone handed off or results scroll differs");
        const auto invalid_input=controller.update_results(token,8,0);
        check(!invalid_input.request_handoff && invalid_input.remaining_input_edges==8,
              "non-original results input triggered handoff");
        const auto accepted=controller.update_results(token,16U|1U,0);
        check(accepted.request_handoff && accepted.remaining_input_edges==0 &&
              controller.state().gate==g1::CampaignControllerGate::next_mission &&
              controller.state().handoff->next_mission_resource==326U,
              "original result mask did not produce the real next mission request");
        rejects([&]{(void)controller.update_results(token,16,0);},"result input replay accepted");
        rejects([&]{controller.report_next_session_installed(token,source);},"unprepared next session accepted");
        rejects([&]{(void)controller.prepare_next_campaign(token,archive(false));},"missing next resource was hidden");
        check(controller.state().gate==g1::CampaignControllerGate::next_mission &&
              same_random(source.random().state(),source_random),"failed preparation consumed handoff or source RNG");
        auto next_context=campaign;next_context.mission_index=1;
        const auto direct=bootstrap_campaign(data,next_context,source.random());
        rejects([&]{(void)controller.prepare_next_campaign(token,archive(true,true));},
                "failure after random spawn was hidden");
        const auto prepared=controller.prepare_next_campaign(token,data);
        check(same_random(prepared.bootstrap.random_after,direct.random_after) &&
              prepared.bootstrap.world.units.front().type==direct.world.units.front().type,
              "failed post-random preparation changed the captured stream on retry");
        check(prepared.context.group==0 && prepared.context.mission_index==1 &&
              prepared.bootstrap.world.mission_resource_id==326 &&
              prepared.bootstrap.random_after.draws>source_random.draws,
              "next campaign lost context or continued random spawn");
        auto expected_random=source.random();
        for(auto draw=source_random.draws;draw<prepared.bootstrap.random_after.draws;++draw)(void)expected_random.next_word();
        check(same_random(expected_random.state(),prepared.bootstrap.random_after),
              "next campaign reseeded instead of continuing exact shared stream");
        const auto cached=controller.prepare_next_campaign(token,data);
        check(same_random(cached.bootstrap.random_after,prepared.bootstrap.random_after),
              "repeated preparation consumed extra random words");
        rejects([&]{(void)controller.prepare_next_campaign(token,data,true);},"cached campaign configuration changed");
        g1::GameSession wrong_random(prepared.bootstrap.world,123,prepared.context);
        rejects([&]{controller.report_next_session_installed(token,wrong_random);},"reseeded installed campaign accepted");
        g1::GameSession installed(data,prepared.bootstrap,prepared.context);
        check(installed.world_presentation().has_value() && installed.mission().gate==g1::MissionGate::camera,
              "next fixture has no real pending presentation/camera gates");
        rejects([&]{controller.report_next_session_installed(token+1,installed);},"stale next-install token accepted");
        controller.report_next_session_installed(token,installed);
        check(controller.state().gate==g1::CampaignControllerGate::handed_off &&
              installed.world_presentation().has_value() && installed.mission().gate==g1::MissionGate::camera,
              "campaign installation fabricated world/camera acknowledgement");
        rejects([&]{controller.report_next_session_installed(token,installed);},"next installation confirmed twice");
        g1::CampaignController reopened(save_path);
        check(g1::encode_campaign_profile(reopened.profile())==saved_bytes,"new controller did not reload persistent profile");

        const auto loss_path=(directory/"loss.g1native").string();
        g1::GameSession lost(data,fixture(data,campaign,1,false),campaign);
        g1::CampaignController loss(loss_path);check(loss.begin(lost).succeeded,"loss profile did not save");
        check(loss.profile().highest_unlocked[0]==0 && loss.profile().records[0][0].value_274==0,
              "loss updated unlock incorrectly or omitted its original record update");
        results_continue(loss);
        check(loss.state().gate==g1::CampaignControllerGate::campaign_menu &&
              loss.state().token!=token,"loss handoff or cross-controller token uniqueness changed");
        rejects([&]{loss.report_ending_presented(loss.state().token);},"menu acknowledged as ending");
        loss.report_menu_presented(loss.state().token);
        check(loss.state().gate==g1::CampaignControllerGate::handed_off,"actual menu presentation did not close request");

        g1::CampaignContext final_context;final_context.mission_index=16;
        g1::GameSession final_session(data,fixture(data,final_context,65535),final_context);
        g1::CampaignController ending((directory/"ending.g1native").string());
        check(ending.begin(final_session).succeeded,"final campaign profile did not save");
        check(ending.profile().completed[0] && ending.profile().highest_unlocked[0]==17 &&
              ending.state().gate==g1::CampaignControllerGate::results,"ending bypassed real results gate");
        results_continue(ending);
        check(ending.state().gate==g1::CampaignControllerGate::campaign_ending &&
              ending.state().handoff->ending_text_resource==0x21ff0390U,"original ending text request differs");
        rejects([&]{ending.report_ending_presented(ending.state().token+1);},"stale ending presentation accepted");
        ending.report_ending_presented(ending.state().token);
        check(ending.state().gate==g1::CampaignControllerGate::handed_off,"ending presentation request not closed");

        g1::CampaignContext group2;group2.group=2;
        g1::GameSession skirmish(data,fixture(data,group2,65534),group2);
        g1::CampaignController immediate((directory/"group2.g1native").string());
        check(immediate.begin(skirmish).succeeded && immediate.state().profile_persisted &&
              !immediate.state().results && immediate.state().gate==g1::CampaignControllerGate::campaign_menu,
              "original group2 immediate post-save handoff was changed");
        immediate.report_menu_presented(immediate.state().token);

        auto not_finished=fixture(data,campaign);not_finished.world.commands={{0,2,6,3,{11,280}}};
        g1::GameSession dialogue(data,std::move(not_finished),campaign);
        g1::CampaignController premature((directory/"premature.g1native").string());
        rejects([&]{(void)premature.begin(dialogue);},"dialogue acknowledgement became campaign completion");
        check(premature.state().gate==g1::CampaignControllerGate::idle && premature.state().save_attempts==0 &&
              !std::filesystem::exists(directory/"premature.g1native"),"invalid campaign gate wrote a profile");
        auto unpresented=fixture(data,campaign);
        unpresented.applied_commands.push_back({0,0,0,g1::WorldPhaseCommand{true,{},{},1}});
        g1::GameSession awaiting_world(data,std::move(unpresented),campaign);
        rejects([&]{(void)premature.begin(awaiting_world);},"prior undrawn world request was bypassed");

        const auto blocked=directory/"rename-target.g1native";
        g1::CampaignController rename_failure(blocked.string());std::filesystem::create_directory(blocked);
        check(!rename_failure.begin(source).succeeded && std::filesystem::is_directory(blocked) &&
              rename_failure.state().gate==g1::CampaignControllerGate::save_failed,
              "actual rename failure reported profile success");
        std::filesystem::remove(blocked);
        check(rename_failure.retry_save(rename_failure.state().token).succeeded,
              "actual rename failure was not retryable");
        const auto corrupt=directory/"corrupt.g1native";
        {std::ofstream output(corrupt,std::ios::binary);output<<"invalid native profile";}
        const auto bad_bytes=g1::read_file(corrupt.string());
        rejects([&]{g1::CampaignController bad(corrupt.string());},"corrupt existing profile silently reset");
        check(g1::read_file(corrupt.string())==bad_bytes,"corrupt profile was overwritten on load failure");
        std::size_t leftovers{};
        for(const auto& entry:std::filesystem::recursive_directory_iterator(directory))
            if(entry.path().filename().string().find(".writing-")!=std::string::npos)++leftovers;
        check(leftovers==0,"controller file failures left temporary save files");
        std::filesystem::remove_all(directory);directory.clear();
        std::cout<<checks<<" campaign orchestration checks passed with real filesystem writes/failures; no UI/device draw claimed.\n";
    }catch(const std::exception& error) {
        if(!directory.empty())std::filesystem::remove_all(directory);
        std::cerr<<"campaign controller: "<<error.what()<<'\n';return 1;
    }
}
