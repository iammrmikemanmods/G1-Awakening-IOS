#include "g1/GameSession.hpp"

#include <iostream>

namespace {
std::size_t checks{};
void check(bool value, const char* message) {
    ++checks;
    if (!value) throw std::runtime_error(message);
}

g1::WorldBootstrap fixture() {
    g1::WorldBootstrap w;
    w.mission_resource_id = 315;
    w.stop = g1::BootstrapStop::presentation_required;
    w.grid = {5,5,g1::Bytes(25,0)};
    w.terrain_rules = {{{{1,0,0}}}};
    for (std::uint8_t type=0;type<23;++type) {
        g1::UnitDefinition definition;
        definition.type=type;
        definition.raw_text_indices[0]=124;
        definition.forms.push_back({2,1,1,60,70,50,0,0,0,0,1,0,0,0});
        definition.forms.push_back({4,1,1,40,50,60,0,0,0,0,0,0,0,0});
        w.unit_definitions.push_back(std::move(definition));
    }
    w.units.push_back({11,0,0,0,1,2,0,true,0});
    w.units.push_back({19,1,1,0,4,4,0,true,0});
    w.initialization_effects={
        {g1::WorldInitializationEffectKind::debit_spawn_funds,0,0,0,{},1},
        {g1::WorldInitializationEffectKind::debit_spawn_funds,0,1,0,{},1}};
    w.sites.push_back({{3,2},-1,{{{2,2}}}});
    const std::vector<std::vector<std::uint16_t>> script{
        {3,11,280},{12,1,245,0,0,0,0},{3,11,288},{8,202}};
    for (std::size_t i=0;i<script.size();++i)
        w.commands.push_back({i,0,script[i].size()*2,script[i][0],
            std::vector<std::uint16_t>(script[i].begin()+1,script[i].end())});
    return w;
}

g1::MissionTickInput advance() {
    // Explicit synthetic renderer fixture, not an actual font/layout claim.
    return {16,g1::DialogueLayout{1,16,14,3,40,true}};
}
}

int main() {
    try {
        auto startup=fixture();
        startup.initialization_effects={
            {g1::WorldInitializationEffectKind::begin_current_player_turn,2,0,0,{}},
            {g1::WorldInitializationEffectKind::debit_spawn_funds,3,0,17,{},1},
            {g1::WorldInitializationEffectKind::debit_spawn_funds,4,1,8,{},1}};
        startup.units[1].spawn={9,true,true};
        g1::GameSession initialized(std::move(startup),1234);
        check(initialized.turn().funds==std::array<std::int32_t,2>{{0,0}} &&
              initialized.turn().human_turn_counter_274==1 &&
              initialized.captures().counters_68==std::array<std::int32_t,2>{{1,1}},
              "ordered initial turn credit and spawn debits changed economy");
        check(initialized.combat_units()[1].health==9 && initialized.combat_units()[1].damage_immune,
              "special scripted placement HP/immunity was lost");
        auto repeated=fixture();
        repeated.initialization_effects.push_back(
            {g1::WorldInitializationEffectKind::debit_spawn_funds,1,0,0,{},1});
        g1::GameSession repeated_session(std::move(repeated),1234);
        check(repeated_session.campaign_context().active_unit_counts==std::array<std::uint8_t,2>{{2,1}},
              "repeated activation count was incorrectly reconstructed from unique roster");
        g1::GameSession session(fixture(),1234);
        check(session.captures().counters_68 == std::array<std::int32_t,2>{{0,0}},
              "cold-start income was invented");
        check(!session.select(0),"script dialogue allowed gameplay selection");
        check(session.move_selected_to({2,2}) == g1::MoveRequestResult::script_controls_input,
              "script dialogue allowed movement");
        (void)session.tick(30,advance());
        check(session.mission().command_index == 0 && session.mission().gate == g1::MissionGate::advance_pending,
              "dialogue consumed dispatch immediately");
        (void)session.tick(30);
        check(session.mission().gate == g1::MissionGate::captured_site_item,
              "goal did not enter gameplay");
        check(!session.select(1),"opponent unit accepted as current-player selection");
        check(session.select(0),"own active unit not selectable");
        check(session.selected_movement_range().has_value(),"movement field missing");
        check(session.move_selected_to({4,4}) == g1::MoveRequestResult::occupied_destination,
              "ordinary movement admitted occupied destination");
        check(session.move_selected_to({9,9}) == g1::MoveRequestResult::outside_map,
              "outside movement admitted");
        check(session.move_selected_to({2,2}) == g1::MoveRequestResult::started,"valid move failed");
        check(!session.selected_can_capture(),"capture admitted during travel");
        check(session.move_selected_to({2,3}) == g1::MoveRequestResult::movement_in_progress,
              "second move admitted while travelling");
        for (int step=0;step<10;++step) (void)session.tick(30);
        check(session.moving(),"one-tile robot movement finished before original11steps");
        check(session.units()[0].spent_budget == 0,"movement charged before arrival");
        const auto arrived = session.tick(30);
        check(arrived.movement_finished && !session.moving(),"movement failed to complete");
        check(session.world().units[0].x == 2 && session.world().units[0].y == 2,
              "world did not receive real move state");
        check(session.units()[0].spent_budget == 1 && session.units()[0].facing == 1,
              "arrival cost/facing not applied");
        check(session.sites()[0].item_states[0][0] == -1 &&
              session.mission().gate == g1::MissionGate::captured_site_item,
              "moving onto objective fabricated capture");
        check(session.move_selected_to({2,3}) == g1::MoveRequestResult::already_moved,
              "remaining budget bypassed one-move admission");
        check(session.selected_can_capture(),"real capture unavailable at objective");
        check(session.capture_selected().status == g1::CaptureStatus::captured,"capture command failed");
        check(session.sites()[0].item_states[0][0] == 0 && session.units()[0].flag_2c == 1,
              "capture did not mutate authentic owner/action state");
        check(session.mission().gate == g1::MissionGate::captured_site_item,
              "capture command directly advanced script");
        (void)session.tick(30);
        check(session.mission().gate == g1::MissionGate::advance_pending &&
              session.units()[0].flag_2c == 0 && session.units()[0].spent_budget == 0,
              "goal observer/action reset not connected");
        (void)session.tick(30);
        check(session.mission().gate == g1::MissionGate::dialogue,"post-capture dialogue missing");
        (void)session.tick(30,advance());
        const auto completion=session.tick(30);
        check(completion.completion.has_value() &&
              session.mission().gate == g1::MissionGate::completion_frame &&
              session.mission().stop == g1::MissionStop::none,
              "actual world state did not enter recovered completion presentation");
        check(!session.end_turn_available(),"completion presentation allowed gameplay input");

        auto battle_world=fixture();
        battle_world.units[1].x=2;battle_world.units[1].y=2;
        battle_world.units[1].spawn.health=1;
        battle_world.unit_definitions[11].forms[0][3]=100;
        battle_world.unit_definitions[11].forms[0][4]=100;
        battle_world.unit_definitions[19].forms[0][5]=0;
        battle_world.commands={{0,0,6,3,{11,280}},{1,0,8,12,{2,245,19}},
                               {2,0,2,1,{}},{3,0,4,8,{202}}};
        g1::GameSession combat_session(std::move(battle_world),4321);
        (void)combat_session.tick(30,advance());
        (void)combat_session.tick(30);
        check(combat_session.select(0),"combat actor selection failed");
        check(combat_session.selected_attack_targets()==std::vector<std::size_t>{1},
              "actual opponent target not exposed");
        check(!combat_session.attack_selected(0),"self attack admitted");
        check(combat_session.attack_selected(1),"actual enemy attack did not start");
        check(combat_session.battle().has_value() && combat_session.battle()->exchange.destroyed.size()==1 &&
              !combat_session.world().units[1].active && !combat_session.units()[1].active &&
              combat_session.combat_units()[1].health==0,
              "combat death did not synchronize native world and occupancy");
        check(combat_session.mission_record().value_278==1 &&
              combat_session.mission_record().value_27c==0 && combat_session.units()[0].flag_2c==1,
              "combat action/counters were not applied");
        check(!combat_session.select(0) && !combat_session.end_turn_available() &&
              combat_session.selected_attack_targets().empty(),"battle presentation did not block input");
        (void)combat_session.tick(30);
        check(combat_session.mission().gate==g1::MissionGate::objective,
              "battle presentation was skipped before observing its result");
        const auto token=combat_session.battle()->token;
        bool rejected=false;
        try {combat_session.report_battle_finished(token+1);} catch(const g1::FormatError&){rejected=true;}
        check(rejected && combat_session.battle().has_value(),"stale battle callback unlocked session");
        combat_session.report_battle_finished(token);
        (void)combat_session.tick(30);
        check(combat_session.mission().gate==g1::MissionGate::advance_pending &&
              combat_session.campaign_context().active_unit_counts[1]==0,
              "real combat objective did not resume script after presentation");

        for (const int refresh : {30,60,120,144}) {
            g1::SimulationClock clock;
            std::uint32_t previous{}, ticks{};
            for (int frame=1;frame<=refresh;++frame) {
                const auto now=std::uint32_t(frame*1000/refresh);
                ticks+=clock.add_elapsed(now-previous);
                previous=now;
            }
            check(ticks == 33,"display refresh changed simulation update count");
            check(clock.interpolation() > 0.3333F && clock.interpolation() < 0.3334F,
                  "display partition lost fractional simulation time");
            clock.reset();
            check(clock.add_elapsed(0)==0 && clock.interpolation()==0,"resume clock retained catch-up time");
            check(clock.add_elapsed(2000)==33,"original1000ms delta bound not respected");
        }
        std::cout << checks << " native session/clock integration checks passed; synthetic mission, not a playthrough\n";
    } catch (const std::exception& e) {
        std::cerr << e.what() << '\n'; return 1;
    }
}
