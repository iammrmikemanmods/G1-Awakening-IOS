#pragma once
#include "g1/TechSpecsModel.hpp"
#include "g1/M3GBattleTimeline.hpp"
#include <limits>

namespace g1 {
// Presentation only. The model's original ready pose is sampled at the same
// time used by native battle setup. No joints, vertex data or game state are
// modified. Original Z-up asset space is converted to tactical Y-up once.
struct TacticalBounds {std::array<float,3> minimum{},maximum{};};
inline M3GMatrix tactical_placement(const TacticalBounds& b, std::uint8_t facing,
                                   float x,float y,float z) {
    if(facing>3 || !std::isfinite(x)||!std::isfinite(y)||!std::isfinite(z))
        throw FormatError("Invalid tactical model placement");
    for(int i=0;i<3;++i)if(!std::isfinite(b.minimum[i])||!std::isfinite(b.maximum[i])||b.maximum[i]<b.minimum[i])
        throw FormatError("Invalid tactical model bounds");
    const float height=b.maximum[2]-b.minimum[2];
    const float width=std::max(b.maximum[0]-b.minimum[0],b.maximum[1]-b.minimum[1]);
    if(height<=0.001F || width<=0.001F || height>1000 || width>1000)
        throw FormatError("Degenerate tactical model extent");
    // Same positive scale for every axis; retain source relative sizes until
    // the footprint limit is reached. Never widen a face or shorten limbs.
    const float s=std::min(0.055F,0.42F/width);
    // Native facing: up=0, down=1, left=2, right=3. Source faces +Y (verified from original textured meshes).
    constexpr float pi=3.14159265358979323846F;
    constexpr float angle[4]={0,pi,pi/2,-pi/2};
    const float c=std::cos(angle[facing]),q=std::sin(angle[facing]);
    const M3GMatrix yaw{{c,0,-q,0, 0,1,0,0, q,0,c,0, x,y,z,1}};
    const M3GMatrix axis{{s,0,0,0, 0,0,-s,0, 0,s,0,0, 0,0,0,1}};
    const M3GMatrix foot{{1,0,0,0, 0,1,0,0, 0,0,1,0,
        -(b.minimum[0]+b.maximum[0])*0.5F,
        -(b.minimum[1]+b.maximum[1])*0.5F,-b.minimum[2],1}};
    return m3g_multiply(m3g_multiply(yaw,axis),foot);
}
inline bool tactical_model_eligible(bool modern,bool active,bool moving,bool transforming,
                                    bool special_presentation) noexcept {
    // Walking/transform clips have not been recovered for the tactical 3D
    // path. Keep the proven original sprite animation rather than gliding a
    // frozen robot or inventing a mesh morph. This gate is intentionally safe.
    return modern && active && !moving && !transforming && !special_presentation;
}
class TacticalModel {
public:
    explicit TacticalModel(const Archive& archive,std::uint8_t type):type_(type) {
        const auto ids=archive.find(tech_specs_model_resource(type),0xf4e02223U);
        if(ids.size()!=1)throw FormatError("Tactical original model missing or ambiguous");
        bytes_=archive.read(ids.front());scene_=std::make_unique<M3GScene>(bytes_);
        M3GNodeBindings bindings(*scene_);
        const auto& objects=scene_->objects();
        const auto world=std::find_if(objects.begin(),objects.end(),[](const auto& o){return o.type==22;});
        if(world==objects.end())throw FormatError("Tactical M3G World missing");
        const auto root=bindings.select_loaded_container_group({world->children.begin(),world->children.end()});
        forms_=bindings.form_nodes(root);asset_=scene_->render_asset(root);
        if(!asset_.sprites.empty())throw FormatError("Tactical mesh has unsupported attached Sprite3D");
        appearance_=m3g_mesh_appearance_order_keys(*scene_);
        for(const auto& item:M3GMaterialBindings(bytes_).plan(root,type)) {
            auto replacement=load_m3g_material_image(archive,item.resource_id);
            if(!item.texture_object)continue;
            const auto key=std::max(scene_->objects().size()+1,
                asset_.geometry.images.empty()?std::size_t(1):asset_.geometry.images.rbegin()->first+1);
            asset_.geometry.images.emplace(key,std::move(replacement.image));
            for(auto& s:asset_.geometry.surfaces)if(s.appearance.texture && s.appearance.texture->texture_object==*item.texture_object) {
                s.appearance.texture->image_object=key;s.appearance.texture->image_format=replacement.image_format;
            }
        }
        std::set<std::size_t> targets;std::vector<std::size_t> todo{root};
        while(!todo.empty()) {
            const auto id=todo.back();todo.pop_back();
            if(!targets.insert(id).second)throw FormatError("Cyclic tactical model subtree");
            const auto found=std::find_if(objects.begin(),objects.end(),[&](const auto& o){return o.index==id;});
            if(found==objects.end())throw FormatError("Missing tactical model descendant");
            todo.insert(todo.end(),found->children.begin(),found->children.end());
        }
        M3GScenePose pose(*scene_,decode_m3g_cameras(bytes_));pose.detach(root);
        pose.apply(M3GAnimations(bytes_).sample_targets(start_m3g_battle_clip(1).animation_time_ms,targets));
        pose.set_rendering_enabled(root,true);
        for(std::uint8_t f=0;f<2;++f) {
            if((f==0 && !forms_.robot)||(f==1 && !forms_.car))continue;
            auto selected=pose;
            if(forms_.robot)selected.set_rendering_enabled(*forms_.robot,f==0);
            if(forms_.car)selected.set_rendering_enabled(*forms_.car,f==1);
            nodes_[f]=selected.evaluated_nodes();
            auto& b=bounds_[f];b.minimum.fill(std::numeric_limits<float>::max());
            b.maximum.fill(std::numeric_limits<float>::lowest());
            std::size_t count=0;
            for(const auto& surface:asset_.geometry.surfaces) {
                const auto& n=nodes_[f].at(surface.mesh_object);
                if(!n.rendering_enabled || n.effective_alpha<=0)continue;
                for(const auto& vertex:surface.vertices)for(int i=0;i<3;++i) {
                    float value=0;for(int j=0;j<4;++j)value+=n.model[j*4+i]*vertex.position[j];
                    if(!std::isfinite(value))throw FormatError("Nonfinite tactical pose");
                    b.minimum[i]=std::min(b.minimum[i],value);b.maximum[i]=std::max(b.maximum[i],value);
                    ++count;
                }
            }
            if(!count)continue;
            (void)tactical_placement(b,1,0,0,0);supported_[f]=true;
        }
        if(!supported_[0])throw FormatError("No valid original robot pose");
    }
    const M3GRenderAsset& asset() const noexcept{return asset_;}
    bool supports(std::uint8_t form) const noexcept{return form<2 && supported_[form];}
    const TacticalBounds& bounds(std::uint8_t form) const {
        if(!supports(form))throw FormatError("Original tactical form not available");return bounds_[form];
    }
    M3GPreparedFrame prepare(const M3GRenderAsset& uploaded,std::uint8_t form,std::uint8_t facing,
                            std::array<float,3> foot,const M3GMatrix& camera,
                            std::array<std::uint32_t,2> pixels) const {
        if(!supports(form))throw FormatError("Original tactical form not available");
        // Preserve GPU asset identity; no copied/rescaled geometry in the plan.
        if(uploaded.geometry.surfaces.size()!=asset_.geometry.surfaces.size())
            throw FormatError("Tactical uploaded asset mismatch");
        M3GRenderInstance instance;instance.asset=&uploaded;instance.nodes=&nodes_[form];instance.identity=1;
        instance.mesh_appearance_serials=&appearance_;
        instance.parent_transform=tactical_placement(bounds_[form],facing,foot[0],foot[1],foot[2]);
        M3GRenderView view{};view.viewport_pixels=pixels;view.projection.type=48;
        view.projection.generic=camera;
        // Undo Metal clip-depth conversion before the shared planner applies
        // it once. The exact same tactical camera then draws terrain and mesh.
        for(int column=0;column<4;++column)
            view.projection.generic[column*4+2]=2*camera[column*4+2]-camera[column*4+3];
        return prepare_m3g_frame({instance},view);
    }
private:
    std::uint8_t type_{};Bytes bytes_;std::unique_ptr<M3GScene> scene_;
    M3GRenderAsset asset_;M3GFormNodeBindings forms_;
    std::map<std::size_t,std::int32_t> appearance_;
    std::array<std::map<std::size_t,M3GEvaluatedNode>,2> nodes_;
    std::array<TacticalBounds,2> bounds_{};std::array<bool,2> supported_{};
};
} // namespace g1
