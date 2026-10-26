    // Development-only counterfactual input search. Checkpoints are restored
    // without edits, and every candidate uses the same public commands as a
    // human. Only the accepted command sequence is replayed into session_.
    static bool apply_tactical_command(g1::GameSession& model,const SearchCommand& command) {
        if(command.kind==SearchCommandKind::end_turn)return bool(model.end_turn());
        if(!model.select(command.actor))return false;
        switch(command.kind) {
        case SearchCommandKind::transform:return bool(model.transform_selected());
        case SearchCommandKind::move:return model.move_selected_to(command.tile)==g1::MoveRequestResult::started;
        case SearchCommandKind::attack:return model.attack_selected(command.target);
        case SearchCommandKind::capture:return model.capture_selected().status==g1::CaptureStatus::captured;
        case SearchCommandKind::heal: {
            const auto result=model.heal_selected(command.target);
            return result && result->outcome==g1::HealOutcome::healed;
        }
        case SearchCommandKind::upgrade:return bool(model.upgrade_selected());
        case SearchCommandKind::produce: {
            if(command.target>=model.world().unit_definitions.size() ||
               !g1::production_affordable(model.world().unit_definitions[command.target],
                                           model.turn().funds[model.current_player()]))return false;
            return bool(model.produce_selected(command.production_mode,
                static_cast<std::uint8_t>(command.target),command.tile,
                g1::ProductionConfirmation::direct_type_list));
        }
        case SearchCommandKind::end_turn:break;
        }
        return false;
    }

    static double tactical_score(const g1::GameSession& model,const std::vector<Goal>& goals) {
        double score{};int own_count{},enemy_count{};
        for(const auto& unit:model.combat_units()) {
            if(!unit.active)continue;
            const auto& definition=model.world().unit_definitions[unit.type];
            const auto robot=g1::combat_stats(definition,0,unit.level);
            const auto vehicle=g1::combat_stats(definition,1,unit.level);
            const double power=180.0+std::max(robot.attack_high,vehicle.attack_high)+
                0.6*std::max(robot.defense,vehicle.defense)+
                8.0*std::max(signed_byte(definition.forms[0][0]),signed_byte(definition.forms[1][0]));
            const auto value=power*(0.25+0.75*unit.health/100.0);
            if(unit.owner==0){++own_count;score+=value;}
            else {++enemy_count;score-=value*1.15;}
        }
        if(own_count==0)return -1.0e9;
        if(enemy_count==0)return 1.0e8+score;
        for(const auto& site:model.sites()) {
            score+=site.state==0 ? 1800.0 : (site.state==1 ? -900.0 : 0.0);
            for(const auto& group:site.item_states)for(auto owner:group)
                score+=owner==0 ? 300.0 : (owner==1 ? -150.0 : 0.0);
        }
        // Money is useful only through legal future actions. Avoid valuing a
        // cash reserve more than the active army it can buy or improve.
        score+=0.75*model.turn().funds[0]-0.4*model.turn().funds[1];
        for(const auto& goal:goals) {
            double nearest=100.0;
            for(const auto& unit:model.combat_units()) {
                if(!unit.active || unit.owner!=0 || (goal.required_type && unit.type!=*goal.required_type))continue;
                const auto& definition=model.world().unit_definitions[unit.type];
                if(goal.capture && definition.forms[0][10]!=1 && definition.forms[1][10]!=1)continue;
                const int speed=std::max(signed_byte(definition.forms[0][0]),signed_byte(definition.forms[1][0]));
                if(speed<=0)continue;
                nearest=std::min(nearest,double(distance({unit.x,unit.y},goal.tile)));
            }
            score-=22.0*nearest;
        }
        return score;
    }

    static bool tactical_goal_reached(const g1::GameSession& model,const g1::MissionObjective& objective) {
        unsigned own{},enemy{};
        for(const auto& unit:model.combat_units())if(unit.active) {
            if(unit.owner==0)++own;else ++enemy;
        }
        if(own==0)return false;
        if(enemy==0)return true;
        const auto& args=objective.parameters;
        if(objective.kind==g1::MissionObjectiveKind::site_owner) {
            if(args[0]>=0)return model.sites().at(static_cast<std::size_t>(args[0])).state==args[1];
            return std::all_of(model.sites().begin(),model.sites().end(),[&](const auto& site){return site.state==args[1];});
        }
        if(objective.kind==g1::MissionObjectiveKind::site_item_owner)
            return g1::captured_site_objective_satisfied({args[0],args[1],args[2],args[3],
                objective.text_index,objective.text_id},model.sites());
        if(objective.kind==g1::MissionObjectiveKind::inactive_unit) {
            if(args[0]>=0) {
                for(const auto& unit:model.combat_units())if(unit.type==args[0])return !unit.active;
                return true;
            }
            const auto faction=args[0]==-1 ? 0 : 1;
            for(const auto& unit:model.combat_units())if(unit.active && unit.faction==faction)return false;
            return true;
        }
        return false;
    }

    static std::vector<SearchNode> tactical_prune(std::vector<SearchNode> nodes,std::size_t limit) {
        std::stable_sort(nodes.begin(),nodes.end(),[](const auto& a,const auto& b){return a.score>b.score;});
        std::unordered_set<std::string> seen;std::vector<SearchNode> result;
        for(auto& node:nodes) {
            std::ostringstream key;
            for(std::size_t i=0;i<node.checkpoint.combat.size();++i) {
                const auto& u=node.checkpoint.combat[i];const auto& m=node.checkpoint.movement[i];
                key<<int(u.type)<<','<<u.active<<','<<int(u.x)<<','<<int(u.y)<<','<<int(u.form)<<','
                   <<int(u.health)<<','<<int(u.level)<<','<<int(m.spent_budget)<<','<<int(m.flag_2c)<<';';
            }
            key<<node.checkpoint.turn.funds[0]<<','<<node.checkpoint.turn.funds[1]<<';';
            for(const auto& site:node.checkpoint.captures.sites) {
                key<<int(site.state)<<';';
                for(const auto& group:site.item_states)for(auto owner:group)key<<int(owner)<<',';
            }
            if(seen.insert(key.str()).second) {result.push_back(std::move(node));if(result.size()==limit)break;}
        }
        return result;
    }

    std::vector<g1::WorldCoordinate> tactical_destinations(g1::GameSession& model,std::size_t actor,
                                                         const std::vector<Goal>& goals) const {
        if(!model.select(actor))return {};
        const auto range=model.selected_movement_range();if(!range)return {};
        const auto board=model.world().movement_board();const auto& unit=model.combat_units()[actor];
        const auto& form=model.world().unit_definitions[unit.type].forms[unit.form];
        struct Candidate {g1::WorldCoordinate tile;double score;};std::vector<Candidate> choices;
        for(std::uint16_t y=0;y<board.height;++y)for(std::uint16_t x=0;x<board.width;++x) {
            const auto cell=std::size_t(y)*board.width+x;
            if(range->remaining[cell]<0 || range->remaining[cell]==127 || board.cells[cell].active_owner>=0)continue;
            const g1::WorldCoordinate tile{static_cast<std::uint8_t>(x),static_cast<std::uint8_t>(y)};
            int nearest=100;for(const auto& goal:goals)nearest=std::min(nearest,distance(tile,goal.tile));
            double value=-5.0*nearest;
            for(const auto& enemy:model.combat_units())if(enemy.active && enemy.owner!=unit.owner) {
                const int d=distance(tile,{enemy.x,enemy.y});
                if(signed_byte(form[3])>0 && d>=signed_byte(form[1]) && d<=signed_byte(form[2]))
                    value+=25.0+(100-enemy.health)*0.1;
                const auto& opposing=model.world().unit_definitions[enemy.type].forms[enemy.form];
                if(signed_byte(opposing[3])>0 && d<=signed_byte(opposing[2])+signed_byte(opposing[0]))value-=8.0;
            }
            for(const auto& goal:goals)if(goal.capture && distance(tile,goal.tile)==0)value+=100.0;
            choices.push_back({tile,value});
        }
        std::stable_sort(choices.begin(),choices.end(),[](const auto& a,const auto& b){return a.score>b.score;});
        std::vector<g1::WorldCoordinate> result;
        for(const auto& choice:choices){result.push_back(choice.tile);if(result.size()==7)break;}
        for(unsigned side=0;side<4 && !choices.empty();++side) {
            const auto best=std::min_element(choices.begin(),choices.end(),[side](const auto& a,const auto& b){
                const int av=side<2 ? a.tile.x : a.tile.y,bv=side<2 ? b.tile.x : b.tile.y;
                return side%2 ? av>bv : av<bv;
            })->tile;
            if(std::none_of(result.begin(),result.end(),[best](auto p){return p.x==best.x && p.y==best.y;}))result.push_back(best);
        }
        return result;
    }

    bool search_tactical_turn() {
        if(!session_->checkpoint_available() || !session_->mission().mission_objective)return false;
        const auto initial_command=session_->mission().command_index;
        const auto objective=*session_->mission().mission_objective;
        const auto goals=goals_for(*session_);const auto began=Clock::now();
        std::size_t evaluated{},accepted{},settle_bounds{};
        std::array<std::size_t,8> accepted_kinds{};
        const auto available=[&](){return evaluated<8000 &&
            std::chrono::duration<double>(Clock::now()-began).count()<6.0;};
        const auto clone=[&](const g1::SessionCheckpoint& checkpoint){
            auto model=g1::GameSession::restore_checkpoint(archive_,checkpoint);model_feedback(*model);return model;
        };
        std::vector<SearchCommand> found;
        const auto advance=[&](const SearchNode& parent,SearchCommand command)->std::optional<SearchNode>{
            if(!available())return {};
            ++evaluated;auto model=clone(parent.checkpoint);
            if(!apply_tactical_command(*model,command))return {};
            ++accepted;++accepted_kinds[static_cast<std::size_t>(command.kind)];
            if(!model_ready(*model,initial_command)){++settle_bounds;return {};}
            auto path=parent.commands;
            if(model->mission().command_index!=initial_command || model->mission().gate!=g1::MissionGate::objective) {
                if(tactical_goal_reached(*model,objective)){path.push_back(std::move(command));found=std::move(path);}
                return {};
            }
            if(!model->checkpoint_available() || model->current_player()!=0)return {};
            auto checkpoint=model->make_checkpoint();command.expected_ready_checkpoint=g1::encode_session_checkpoint(checkpoint);
            path.push_back(std::move(command));
            return SearchNode{std::move(checkpoint),std::move(path),tactical_score(*model,goals)};
        };
        const SearchNode start{session_->make_checkpoint(),{},tactical_score(*session_,goals)};
        if(session_->turn().human_turn_counter_274==1 || session_->turn().human_turn_counter_274==20) {
            auto diagnostic=clone(start.checkpoint);
            for(std::size_t i=0;i<diagnostic->units().size();++i) {
                if(!diagnostic->units()[i].active || diagnostic->world().units[i].owner!=0 || !diagnostic->select(i))continue;
                const auto type=diagnostic->world().units[i].type;
                const auto& definition=diagnostic->world().unit_definitions[type];
                std::ostringstream fields;fields<<"\"type\":"<<unsigned(type)<<",\"forms\":[";
                for(std::size_t f=0;f<2;++f) {if(f)fields<<',';fields<<'[';
                    for(std::size_t n=0;n<definition.forms[f].size();++n){if(n)fields<<',';fields<<signed_byte(definition.forms[f][n]);}
                    fields<<']';}
                fields<<"],\"upgrade_eligibility\":"<<int(diagnostic->selected_upgrade_eligibility())
                    <<",\"production_candidates\":"<<diagnostic->selected_production_candidates(g1::ProductionMode::ordinary).size()
                    <<",\"deploy_candidates\":"<<diagnostic->selected_production_candidates(g1::ProductionMode::deploy).size()
                    <<",\"transform_eligibility\":"<<int(diagnostic->selected_transform_eligibility());
                event("tactical_actor_diagnostic",fields.str());
            }
        }
        std::optional<SearchNode> best=advance(start,{SearchCommandKind::end_turn,0,{},{}});
        std::vector<std::size_t> actors;
        for(std::size_t i=0;i<session_->units().size();++i)
            if(session_->units()[i].active && session_->world().units[i].owner==0)actors.push_back(i);
        // Higher potential attackers first; the original type still breaks ties.
        std::stable_sort(actors.begin(),actors.end(),[&](auto a,auto b){
            const auto& left=session_->combat_units()[a];const auto& right=session_->combat_units()[b];
            const auto lp=g1::combat_stats(session_->world().unit_definitions[left.type],0,left.level).attack_high;
            const auto rp=g1::combat_stats(session_->world().unit_definitions[right.type],0,right.level).attack_high;
            return lp!=rp ? lp>rp : left.type<right.type;
        });
        std::vector<SearchNode> partial{start};
        for(auto actor:actors) {
            std::vector<SearchNode> expanded;
            for(const auto& node:partial) {
                if(!available() || !found.empty())break;
                auto model=clone(node.checkpoint);
                if(!model->units()[actor].active || model->units()[actor].flag_2c || !model->select(actor)) {
                    expanded.push_back(node);continue;
                }
                std::vector<SearchNode> forms{node};
                if(model->selected_transform_eligibility()==g1::TransformEligibility::allowed) {
                    auto transformed=advance(node,{SearchCommandKind::transform,actor,{},{}});
                    if(transformed)forms.push_back(std::move(*transformed));
                }
                std::vector<SearchNode> positions;
                for(const auto& form:forms) {
                    positions.push_back(form);auto posed=clone(form.checkpoint);
                    for(auto tile:tactical_destinations(*posed,actor,goals)) {
                        auto moved=advance(form,{SearchCommandKind::move,actor,tile,{}});
                        if(moved)positions.push_back(std::move(*moved));
                        if(!available() || !found.empty())break;
                    }
                }
                for(const auto& position:positions) {
                    if(!available() || !found.empty())break;
                    expanded.push_back(position);auto posed=clone(position.checkpoint);
                    if(!posed->select(actor))continue;
                    std::vector<SearchCommand> actions;
                    if(posed->selected_can_capture())actions.push_back({SearchCommandKind::capture,actor,{},{}});
                    for(auto target:posed->selected_attack_targets())actions.push_back({SearchCommandKind::attack,actor,{},{},target});
                    if(posed->selected_upgrade_eligibility()==g1::UpgradeEligibility::allowed)
                        actions.push_back({SearchCommandKind::upgrade,actor,{},{}});
                    for(auto target:posed->selected_heal_targets())if(posed->combat_units()[target].health<90)
                        actions.push_back({SearchCommandKind::heal,actor,{},{},target});
                    for(auto mode:{g1::ProductionMode::deploy,g1::ProductionMode::ordinary}) {
                        auto candidates=posed->selected_production_candidates(mode);
                        const auto placement=posed->selected_production_placement(mode);if(!placement)continue;
                        candidates.erase(std::remove_if(candidates.begin(),candidates.end(),[&](auto type){
                            return !g1::production_affordable(posed->world().unit_definitions[type],posed->turn().funds[0]);
                        }),candidates.end());
                        std::stable_sort(candidates.begin(),candidates.end(),[&](auto a,auto b){
                            const auto& defs=posed->world().unit_definitions;
                            return signed_byte(defs[a].forms[0][4])>signed_byte(defs[b].forms[0][4]);
                        });
                        if(candidates.size()>2)candidates.resize(2);
                        const auto board=posed->world().movement_board();
                        for(auto type:candidates)for(std::uint16_t y=0;y<board.height;++y)for(std::uint16_t x=0;x<board.width;++x) {
                            const auto cell=std::size_t(y)*board.width+x;
                            if(placement->range.remaining[cell]<0 || placement->range.remaining[cell]==127 || board.cells[cell].active_owner>=0)continue;
                            actions.push_back({SearchCommandKind::produce,actor,{static_cast<std::uint8_t>(x),static_cast<std::uint8_t>(y)},{},type,mode});
                        }
                    }
                    for(auto action:actions) {
                        auto acted=advance(position,std::move(action));if(acted)expanded.push_back(std::move(*acted));
                        if(!available() || !found.empty())break;
                    }
                }
            }
            if(!found.empty())break;
            if(expanded.empty())break;
            // Preserve choices which survive the real opponent response,
            // rather than retaining only attractive but exposed positions.
            // The preview is discarded; node.checkpoint is never edited.
            auto candidates=tactical_prune(std::move(expanded),32);
            for(auto& candidate:candidates) {
                auto preview=advance(candidate,{SearchCommandKind::end_turn,0,{},{}});
                if(preview) {
                    candidate.score=preview->score;
                    if(!best || preview->score>best->score)best=std::move(preview);
                } else candidate.score=-1.0e10;
                if(!available() || !found.empty())break;
            }
            partial=tactical_prune(std::move(candidates),8);
            if(!available())break;
        }
        if(found.empty())for(const auto& node:partial) {
            if(!available())break;
            auto ended=advance(node,{SearchCommandKind::end_turn,0,{},{}});
            if(ended && (!best || ended->score>best->score))best=std::move(ended);
            if(!found.empty())break;
        }
        std::ostringstream kind_counts;kind_counts<<'[';
        for(std::size_t k=0;k<accepted_kinds.size();++k){if(k)kind_counts<<',';kind_counts<<accepted_kinds[k];}
        kind_counts<<']';
        event("tactical_turn_search","\"branch_command_evaluations\":"+std::to_string(evaluated)+
            ",\"accepted_commands\":"+std::to_string(accepted)+",\"settle_bounds\":"+std::to_string(settle_bounds)+
            ",\"objective_reached\":"+(found.empty() ? "false" : "true")+
            ",\"budget_reached\":"+(available() ? "false" : "true")+
            ",\"before_score\":"+std::to_string(start.score)+",\"chosen_score\":"+
            (best ? std::to_string(best->score) : "null")+",\"accepted_by_kind\":"+kind_counts.str()+",\"state_transplanted\":false");
        counts_.search_commands+=evaluated;counts_.search_accepted+=accepted;counts_.search_settle_bounds+=settle_bounds;
        if(!found.empty())tactical_commands_=std::move(found);
        else if(best)tactical_commands_=std::move(best->commands);
        else return false;
        tactical_cursor_=0;++counts_.search_solutions;return true;
    }

    bool replay_tactical_command() {
        if(!expected_tactical_checkpoint_.empty()) {
            if(!session_->checkpoint_available() ||
               g1::encode_session_checkpoint(session_->make_checkpoint())!=expected_tactical_checkpoint_)
                throw g1::FormatError("Tactical test-input replay diverged from its public-command simulation");
            ++counts_.replay_checkpoint_matches;expected_tactical_checkpoint_.clear();
        }
        if(tactical_cursor_>=tactical_commands_.size())return false;
        const auto& command=tactical_commands_[tactical_cursor_++];
        if(!apply_tactical_command(*session_,command))throw g1::FormatError("Tactical test-input replay command rejected");
        ++counts_.commands;if(command.kind!=SearchCommandKind::end_turn)++counts_.selections;
        const auto actor=command.kind==SearchCommandKind::end_turn ? 255U : session_->world().units[command.actor].type;
        switch(command.kind) {
        case SearchCommandKind::move:++counts_.moves;break;
        case SearchCommandKind::transform:++counts_.transforms;break;
        case SearchCommandKind::attack:++counts_.attacks;break;
        case SearchCommandKind::capture:++counts_.captures;break;
        case SearchCommandKind::heal:++counts_.heals;break;
        case SearchCommandKind::upgrade:++counts_.upgrades;break;
        case SearchCommandKind::produce:++counts_.productions;break;
        case SearchCommandKind::end_turn:++counts_.human_end_turns;reset_input_turn();break;
        }
        event("human_search_command","\"kind\":"+std::to_string(int(command.kind))+
            ",\"actor_type\":"+std::to_string(actor)+",\"target\":"+std::to_string(command.target)+
            ",\"x\":"+std::to_string(command.tile.x)+",\"y\":"+std::to_string(command.tile.y));
        expected_tactical_checkpoint_=command.expected_ready_checkpoint;return true;
    }
