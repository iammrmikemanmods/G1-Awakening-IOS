#import <UIKit/UIKit.h>
#import <MetalKit/MetalKit.h>
#import <QuartzCore/QuartzCore.h>
#import <CommonCrypto/CommonDigest.h>
#include <sys/utsname.h>

#include "MetalRenderer.hpp"
#include "g1/SpriteAnimation.hpp"
#include "g1/InitialPresentation.hpp"

#include <algorithm>
#include <cmath>
#include <deque>
#include <limits>

namespace {
constexpr char archive_sha[] = "663d2888982093ce66b7811ccb7a6ad3acd37fc02ffa85144775b88c39e83cb4";
constexpr char tables_sha[] = "b870e3d74244741003c8068178e7f58bb5fbe35599599c918e024227463725a8";

void verify_sha(const g1::Bytes& data, const char* expected) {
    unsigned char digest[CC_SHA256_DIGEST_LENGTH];
    CC_SHA256(data.data(), static_cast<CC_LONG>(data.size()), digest);
    constexpr char hex[] = "0123456789abcdef";
    std::string actual;
    for (const auto byte : digest) { actual += hex[byte >> 4]; actual += hex[byte & 15]; }
    if (actual != expected) throw g1::FormatError("Bundled game data failed its SHA256 check");
}

std::array<float, 4> transform(const g1::Matrix4& matrix, std::array<float, 4> point) {
    std::array<float, 4> result{};
    for (std::size_t row = 0; row < 4; ++row)
        for (std::size_t column = 0; column < 4; ++column)
            result[row] += matrix[column * 4 + row] * point[column];
    return result;
}

// Explicit inspection camera. Original camera setup is a separate recovery
// task; this view must not be used as evidence of original camera parity.
struct InspectionCamera {
    float center_x{}, center_z{}, span{5}, base_span{5}, aspect{2};
    static constexpr float up_y = 0.7071067811865476F;
    static constexpr float up_z = -0.7071067811865476F;

    void fit(const g1::FirstMissionScene& scene, CGSize size) {
        if (size.width <= 0 || size.height <= 0) return;
        aspect = static_cast<float>(size.width / size.height);
        center_x = scene.world.grid.width * 0.16F;
        center_z = scene.world.grid.height * 0.16F;
        base_span = 1.15F * std::max(scene.world.grid.height * 0.32F * -up_z + 0.6F,
                                   (scene.world.grid.width * 0.32F + 0.8F) / aspect);
        span = base_span;
    }

    g1::Matrix4 matrix() const {
        g1::Matrix4 result{};
        result[0] = 2 / (span * aspect);
        result[5] = 2 * up_y / span;
        result[9] = 2 * up_z / span;
        result[6] = up_z / 100;
        result[10] = -up_y / 100;
        result[12] = -center_x * result[0];
        result[13] = -center_z * result[9];
        result[14] = 0.5F - center_z * result[10];
        result[15] = 1;
        return result;
    }
};

struct FrameStats {
    std::deque<double> times;
    std::uint64_t total{};
    void add(double time) {
        if (time <= 0) return;
        if (!times.empty() && time <= times.back()) return;
        if (!times.empty() && time - times.back() > 1) times.clear();
        times.push_back(time);
        if (times.size() > 181) times.pop_front();
        ++total;
    }
    double fps() const {
        return times.size() > 1 ? (times.size() - 1) / (times.back() - times.front()) : 0;
    }
    double interval_percentile(double percentile) const {
        if (times.size() < 2) return 0;
        std::vector<double> values;
        for (std::size_t i = 1; i < times.size(); ++i)
            values.push_back((times[i] - times[i - 1]) * 1000);
        std::sort(values.begin(), values.end());
        return values[static_cast<std::size_t>(percentile * (values.size() - 1))];
    }
};
} // namespace

@interface G1ViewController : UIViewController <MTKViewDelegate>
@end

@implementation G1ViewController {
    MTKView* _metalView;
    id<MTLCommandQueue> _queue;
    NSMutableDictionary<NSNumber*, id<MTLTexture>>* _textures;
    id<MTLTexture> _white;
    UILabel* _title;
    UILabel* _hint;
    UILabel* _fps;
    UIButton* _reportButton;
    std::unique_ptr<g1::MetalRenderer> _renderer;
    std::unique_ptr<g1::FirstMissionScene> _scene;
    std::shared_ptr<g1::MetalMesh> _terrain, _range;
    std::vector<std::vector<std::vector<g1::SceneVertex>>> _spriteVertices;
    std::vector<std::vector<std::shared_ptr<g1::MetalMesh>>> _spriteMeshes;
    std::vector<g1::SpriteAnimation> _animations;
    std::vector<g1::Matrix4> _unitModels;
    InspectionCamera _camera;
    FrameStats _frameStats;
    double _clockOrigin, _lastHudTime;
    std::uint32_t _lastTick;
    NSInteger _selected;
    bool _clockStarted, _loaded, _failed;
    NSString* _failure;
}

- (BOOL)prefersStatusBarHidden { return YES; }
- (UIInterfaceOrientationMask)supportedInterfaceOrientations { return UIInterfaceOrientationMaskLandscape; }

- (void)viewDidLoad {
    [super viewDidLoad];
    _selected = -1;
    self.view.backgroundColor = [UIColor colorWithRed:0.025 green:0.04 blue:0.065 alpha:1];
    id<MTLDevice> device = MTLCreateSystemDefaultDevice();
    _metalView = [[MTKView alloc] initWithFrame:self.view.bounds device:device];
    _metalView.translatesAutoresizingMaskIntoConstraints = NO;
    _metalView.colorPixelFormat = MTLPixelFormatBGRA8Unorm;
    _metalView.depthStencilPixelFormat = MTLPixelFormatDepth32Float;
    _metalView.autoResizeDrawable = NO;
    _metalView.clearColor = MTLClearColorMake(0.025,0.04,0.065,1);
    _metalView.preferredFramesPerSecond = 60;
    _metalView.paused = YES;
    _metalView.delegate = self;
    [self.view addSubview:_metalView];
    [NSLayoutConstraint activateConstraints:@[
        [_metalView.leadingAnchor constraintEqualToAnchor:self.view.leadingAnchor],
        [_metalView.trailingAnchor constraintEqualToAnchor:self.view.trailingAnchor],
        [_metalView.topAnchor constraintEqualToAnchor:self.view.topAnchor],
        [_metalView.bottomAnchor constraintEqualToAnchor:self.view.bottomAnchor]]];

    _title = [UILabel new];
    _title.text = @"G1 Awakening · Native scene test";
    _title.font = [UIFont systemFontOfSize:17 weight:UIFontWeightSemibold];
    _title.textColor = UIColor.whiteColor;
    _hint = [UILabel new];
    _hint.text = @"Loading the first mission…";
    _hint.font = [UIFont systemFontOfSize:12 weight:UIFontWeightMedium];
    _hint.textColor = [UIColor colorWithWhite:0.85 alpha:1];
    _hint.numberOfLines = 3;
    UIStackView* headings = [[UIStackView alloc] initWithArrangedSubviews:@[_title,_hint]];
    headings.axis = UILayoutConstraintAxisVertical;
    headings.spacing = 4;
    headings.translatesAutoresizingMaskIntoConstraints = NO;
    [self.view addSubview:headings];

    _fps = [UILabel new];
    _fps.text = @"Target: 60 Hz · No device measurement yet";
    _fps.font = [UIFont monospacedDigitSystemFontOfSize:11 weight:UIFontWeightRegular];
    _fps.textColor = [UIColor colorWithWhite:0.8 alpha:1];
    _fps.translatesAutoresizingMaskIntoConstraints = NO;
    [self.view addSubview:_fps];

    UIButton* reset = [UIButton buttonWithType:UIButtonTypeSystem];
    [reset setTitle:@"Reset view" forState:UIControlStateNormal];
    [reset addTarget:self action:@selector(resetView) forControlEvents:UIControlEventTouchUpInside];
    _reportButton = [UIButton buttonWithType:UIButtonTypeSystem];
    [_reportButton setTitle:@"Share test report" forState:UIControlStateNormal];
    [_reportButton addTarget:self action:@selector(shareReport) forControlEvents:UIControlEventTouchUpInside];
    UIStackView* buttons = [[UIStackView alloc] initWithArrangedSubviews:@[reset,_reportButton]];
    buttons.spacing = 18;
    buttons.translatesAutoresizingMaskIntoConstraints = NO;
    [self.view addSubview:buttons];
    UILayoutGuide* safe = self.view.safeAreaLayoutGuide;
    [NSLayoutConstraint activateConstraints:@[
        [headings.leadingAnchor constraintEqualToAnchor:safe.leadingAnchor constant:16],
        [headings.topAnchor constraintEqualToAnchor:safe.topAnchor constant:10],
        [headings.trailingAnchor constraintLessThanOrEqualToAnchor:safe.trailingAnchor constant:-16],
        [_fps.leadingAnchor constraintEqualToAnchor:safe.leadingAnchor constant:16],
        [_fps.bottomAnchor constraintEqualToAnchor:safe.bottomAnchor constant:-10],
        [buttons.trailingAnchor constraintEqualToAnchor:safe.trailingAnchor constant:-16],
        [buttons.bottomAnchor constraintEqualToAnchor:safe.bottomAnchor constant:-4]]];

    [_metalView addGestureRecognizer:[[UITapGestureRecognizer alloc]
        initWithTarget:self action:@selector(tap:)]];
    [_metalView addGestureRecognizer:[[UIPanGestureRecognizer alloc]
        initWithTarget:self action:@selector(pan:)]];
    [_metalView addGestureRecognizer:[[UIPinchGestureRecognizer alloc]
        initWithTarget:self action:@selector(pinch:)]];
    [[NSNotificationCenter defaultCenter] addObserver:self selector:@selector(inactive:)
        name:UIApplicationWillResignActiveNotification object:nil];
    [[NSNotificationCenter defaultCenter] addObserver:self selector:@selector(active:)
        name:UIApplicationDidBecomeActiveNotification object:nil];

    try {
        _renderer = std::make_unique<g1::MetalRenderer>(device);
        _queue = [device newCommandQueue];
        if (!_queue) throw std::runtime_error("Metal command queue is unavailable");
        NSString* path = [NSBundle.mainBundle.bundlePath stringByAppendingPathComponent:@"GameData"];
        auto archiveBytes = g1::read_file([[path stringByAppendingPathComponent:@"iphone.big"] UTF8String]);
        auto tableBytes = g1::read_file([[path stringByAppendingPathComponent:@"terrain-tables.bin"] UTF8String],480);
        verify_sha(archiveBytes, archive_sha);
        verify_sha(tableBytes, tables_sha);
        const g1::Archive archive(std::move(archiveBytes));
        _scene = std::make_unique<g1::FirstMissionScene>(archive,tableBytes);
        _terrain = _renderer->mesh(g1::terrain_vertices(_scene->terrain));
        _textures = [NSMutableDictionary new];
        for (const auto& entry : _scene->textures)
            _textures[@(entry.first)] = _renderer->texture(entry.second);
        _white = _renderer->texture({1,1,{255,255,255,255}});
        const auto presentation = g1::initial_presentations(archive,*_scene);
        if (presentation.size() != _scene->sprites.size())
            throw std::runtime_error("Initial sprite presentation count mismatch");
        for (std::size_t i = 0; i < _scene->sprites.size(); ++i) {
            const auto& sprite = _scene->sprites[i];
            const auto& initial = presentation[i];
            if (initial.animation >= sprite.descriptor.animations().size())
                throw std::runtime_error("Initial sprite animation is outside descriptor");
            _animations.emplace_back(sprite.descriptor.animations()[initial.animation],
                                     initial.repeats,initial.reverse);
            _unitModels.push_back(initial.model);
            std::vector<std::vector<g1::SceneVertex>> frames;
            std::vector<std::shared_ptr<g1::MetalMesh>> meshes;
            for (std::size_t frame = 0; frame < sprite.descriptor.frames().size(); ++frame) {
                frames.push_back(g1::sprite_vertices(sprite.descriptor,frame));
                meshes.push_back(_renderer->mesh(frames.back()));
            }
            _spriteVertices.push_back(std::move(frames));
            _spriteMeshes.push_back(std::move(meshes));
        }
        _loaded = true;
        [self resetView];
        _hint.text = @"Tap a unit for its movement range. Drag or pinch to inspect.\nCampaign controls are unfinished.";
        _metalView.paused = NO;
    } catch (const std::exception& error) {
        [self fail:[NSString stringWithUTF8String:error.what()]];
    }
}

- (void)dealloc { [[NSNotificationCenter defaultCenter] removeObserver:self]; }

- (void)fail:(NSString*)message {
    _failed = true;
    _failure = [message copy];
    _metalView.paused = YES;
    _title.text = @"Native scene test could not start";
    _hint.text = message;
    _hint.textColor = [UIColor colorWithRed:1 green:0.6 blue:0.55 alpha:1];
}

- (void)inactive:(NSNotification*)notification {
    (void)notification;
    _metalView.paused = YES;
    _clockStarted = false;
    _frameStats.times.clear();
}

- (void)active:(NSNotification*)notification {
    (void)notification;
    _clockStarted = false;
    if (_loaded && !_failed) _metalView.paused = NO;
}

- (void)resetView {
    if (!_scene) return;
    _camera.fit(*_scene,_metalView.bounds.size);
}

- (void)viewDidLayoutSubviews {
    [super viewDidLayoutSubviews];
    UIScreen* screen = self.view.window.screen ?: UIScreen.mainScreen;
    // Allocate the render target at the attached display's native pixel scale,
    // not the old game's 480x320 framebuffer size. UIKit controls stay in points.
    if (_metalView.contentScaleFactor != screen.nativeScale)
        _metalView.contentScaleFactor = screen.nativeScale;
    const CGSize nativeSize = CGSizeMake(std::round(_metalView.bounds.size.width * screen.nativeScale),
                                          std::round(_metalView.bounds.size.height * screen.nativeScale));
    if (!CGSizeEqualToSize(_metalView.drawableSize,nativeSize)) _metalView.drawableSize = nativeSize;
    _metalView.preferredFramesPerSecond = screen.maximumFramesPerSecond;
}

- (void)mtkView:(MTKView*)view drawableSizeWillChange:(CGSize)size {
    (void)view;
    if (_scene) _camera.fit(*_scene,size);
}

- (void)pan:(UIPanGestureRecognizer*)gesture {
    if (!_loaded || _metalView.bounds.size.height <= 0) return;
    const CGPoint delta = [gesture translationInView:_metalView];
    const float scale = _camera.span / static_cast<float>(_metalView.bounds.size.height);
    _camera.center_x -= static_cast<float>(delta.x) * scale;
    _camera.center_z += static_cast<float>(delta.y) * scale / InspectionCamera::up_z;
    [gesture setTranslation:CGPointZero inView:_metalView];
}

- (void)pinch:(UIPinchGestureRecognizer*)gesture {
    if (!_loaded) return;
    if (gesture.scale > 0)
        _camera.span = std::clamp(_camera.span / static_cast<float>(gesture.scale),
                                  _camera.base_span * 0.2F, _camera.base_span * 3.0F);
    gesture.scale = 1;
}

- (void)tap:(UITapGestureRecognizer*)gesture {
    if (!_loaded || _failed) return;
    try {
        const auto point = [gesture locationInView:_metalView];
        const auto size = _metalView.bounds.size;
        _selected = -1;
        double best = std::numeric_limits<double>::max();
        for (std::size_t i = 0; i < _animations.size(); ++i) {
            const auto matrix = g1::multiply_matrix(_camera.matrix(),_unitModels[i]);
            CGRect bounds = CGRectNull;
            for (const auto& vertex : _spriteVertices[i][_animations[i].current_frame()]) {
                const auto p = transform(matrix,vertex.position);
                const double x = (p[0] / p[3] * 0.5 + 0.5) * size.width;
                const double y = (0.5 - p[1] / p[3] * 0.5) * size.height;
                bounds = CGRectUnion(bounds,CGRectMake(x,y,0.1,0.1));
            }
            if (!CGRectIsNull(bounds) && CGRectContainsPoint(CGRectInset(bounds,-14,-14),point)) {
                const double distance = std::hypot(point.x - CGRectGetMidX(bounds),
                                                    point.y - CGRectGetMidY(bounds));
                if (distance < best) { best = distance; _selected = static_cast<NSInteger>(i); }
            }
        }
        _range.reset();
        if (_selected < 0) {
            _hint.text = @"Tap a unit for its movement range. Drag or pinch to inspect.\nCampaign controls are unfinished.";
            return;
        }
        const auto index = _scene->sprites[static_cast<std::size_t>(_selected)].unit_index;
        const auto& unit = _scene->world.units[index];
        const auto profile = _scene->world.movement_profile(index);
        const auto range = g1::compute_movement_range(_scene->world.movement_board(),profile,unit.x,unit.y);
        g1::TerrainMesh selected;
        selected.position_scale = _scene->terrain.position_scale;
        for (const auto& quad : _scene->terrain.quads)
            if (quad.face == g1::TerrainFace::top && range.at(quad.tile_x,quad.tile_y) >= 0)
                selected.quads.push_back(quad);
        auto vertices = g1::terrain_vertices(selected);
        for (auto& vertex : vertices) { vertex.position[1] += 0.003F; vertex.uv = {{0,0}}; }
        _range = _renderer->mesh(vertices);
        _hint.text = [NSString stringWithFormat:@"Movement budget: %u · Range preview only\nCampaign controls are unfinished.",
            unsigned(g1::remaining_movement_budget(profile))];
    } catch (const std::exception& error) {
        [self fail:[NSString stringWithUTF8String:error.what()]];
    }
}

- (void)recordPresentation:(double)time {
    if (_metalView.paused) return;
    _frameStats.add(time);
    if (time - _lastHudTime < 0.5 || _frameStats.times.size() < 2) return;
    _lastHudTime = time;
    _fps.text = [NSString stringWithFormat:@"%.1f presented fps · target %ld",_frameStats.fps(),
        static_cast<long>(_metalView.preferredFramesPerSecond)];
}

- (void)drawInMTKView:(MTKView*)view {
    if (!_loaded || _failed) return;
    @autoreleasepool {
        try {
            id<CAMetalDrawable> drawable = view.currentDrawable;
            MTLRenderPassDescriptor* pass = view.currentRenderPassDescriptor;
            if (!drawable || !pass) return;
            const double now = CACurrentMediaTime();
            if (!_clockStarted) { _clockOrigin = now; _lastTick = 0; _clockStarted = true; }
            const auto tick = static_cast<std::uint32_t>(
                static_cast<std::uint64_t>((now - _clockOrigin) * 1000.0));
            // Original core uses integer milliseconds and a default 1000ms
            // maximum delta. Display refresh is never used as a game tick.
            const auto delta = std::min(std::uint32_t(tick - _lastTick),std::uint32_t(1000));
            _lastTick = tick;
            for (auto& animation : _animations) animation.advance_ms(delta);
            const auto camera = _camera.matrix();
            std::vector<g1::MetalDraw> draws{
                {_terrain,_textures[@(_scene->terrain.atlas_resource_id)],camera,{{1,1,1,1}},true}};
            if (_range) draws.push_back({_range,_white,camera,{{0.12F,0.9F,0.85F,0.36F}},false});
            std::vector<std::size_t> order;
            for (std::size_t i = 0; i < _animations.size(); ++i) order.push_back(i);
            std::stable_sort(order.begin(),order.end(),[&](std::size_t a,std::size_t b) {
                const auto pa = transform(g1::multiply_matrix(camera,_unitModels[a]),{{0,0,0,1}});
                const auto pb = transform(g1::multiply_matrix(camera,_unitModels[b]),{{0,0,0,1}});
                return pa[2] > pb[2];
            });
            for (const auto i : order) {
                const auto texture = _textures[@(_scene->sprites[i].resource.image_id)];
                draws.push_back({_spriteMeshes[i][_animations[i].current_frame()],texture,
                    g1::multiply_matrix(camera,_unitModels[i]),{{1,1,1,1}},true});
            }
            id<MTLCommandBuffer> command = [_queue commandBuffer];
            _renderer->encode(command,pass,draws);
            __weak G1ViewController* weakSelf = self;
            [drawable addPresentedHandler:^(id<MTLDrawable> presented) {
                const double time = presented.presentedTime;
                dispatch_async(dispatch_get_main_queue(),^{ [weakSelf recordPresentation:time]; });
            }];
            [command addCompletedHandler:^(id<MTLCommandBuffer> completed) {
                if (completed.status == MTLCommandBufferStatusError) {
                    NSString* reason = completed.error.localizedDescription ?: @"Metal command failed";
                    dispatch_async(dispatch_get_main_queue(),^{ [weakSelf fail:reason]; });
                }
            }];
            [command presentDrawable:drawable];
            [command commit];
        } catch (const std::exception& error) {
            [self fail:[NSString stringWithUTF8String:error.what()]];
        }
    }
}

- (void)shareReport {
    struct utsname system{};
    uname(&system);
    NSDictionary* info = NSBundle.mainBundle.infoDictionary;
    NSDictionary* report = @{
        @"artifact_kind": @"native scene test", @"source_commit": info[@"G1SourceCommit"] ?: @"unknown",
        @"app_version": info[@"CFBundleShortVersionString"] ?: @"unknown",
        @"device": [NSString stringWithUTF8String:system.machine], @"ios": UIDevice.currentDevice.systemVersion,
        @"native_scene_loaded": @(_loaded), @"failure": _failure ?: NSNull.null,
        @"archive_sha256": [NSString stringWithUTF8String:archive_sha],
        @"terrain_tables_sha256": [NSString stringWithUTF8String:tables_sha],
        @"fps_requested": @(_metalView.preferredFramesPerSecond),
        @"drawable_width_pixels": @(_metalView.drawableSize.width),
        @"drawable_height_pixels": @(_metalView.drawableSize.height),
        @"screen_native_scale": @((self.view.window.screen ?: UIScreen.mainScreen).nativeScale),
        @"presented_frames_total": @(_frameStats.total),
        @"presented_interval_samples": @(_frameStats.times.size() > 0 ? _frameStats.times.size() - 1 : 0),
        @"presented_fps_window": @(_frameStats.fps()),
        @"presented_interval_median_ms": @(_frameStats.interval_percentile(0.5)),
        @"presented_interval_p95_ms": @(_frameStats.interval_percentile(0.95)),
        @"camera": @"inspection camera; original camera fidelity unverified",
        @"campaign_cursor": @(_scene ? _scene->world.next_command_index : 0),
        @"full_gameplay_implemented": @NO, @"full_campaign_verified": @NO,
        @"native_save_reload_verified": @NO,
        @"measurement_scope": @"Recent presented frames in this scene only; not full-game performance"
    };
    NSError* error = nil;
    NSData* json = [NSJSONSerialization dataWithJSONObject:report
        options:NSJSONWritingPrettyPrinted | NSJSONWritingSortedKeys error:&error];
    NSURL* file = [NSURL fileURLWithPath:[NSTemporaryDirectory()
        stringByAppendingPathComponent:@"G1-Native-Scene-Report.json"]];
    if (!json || ![json writeToURL:file options:NSDataWritingAtomic error:&error]) {
        _hint.text = error.localizedDescription ?: @"Could not save the test report";
        return;
    }
    UIActivityViewController* sheet = [[UIActivityViewController alloc]
        initWithActivityItems:@[file] applicationActivities:nil];
    sheet.popoverPresentationController.sourceView = _reportButton;
    sheet.popoverPresentationController.sourceRect = _reportButton.bounds;
    [self presentViewController:sheet animated:YES completion:nil];
}
@end

@interface G1AppDelegate : UIResponder <UIApplicationDelegate>
@property(nonatomic,strong) UIWindow* window;
@end
@implementation G1AppDelegate
- (BOOL)application:(UIApplication*)application didFinishLaunchingWithOptions:(NSDictionary*)options {
    (void)application; (void)options;
    self.window = [[UIWindow alloc] initWithFrame:UIScreen.mainScreen.bounds];
    self.window.rootViewController = [G1ViewController new];
    [self.window makeKeyAndVisible];
    return YES;
}
@end

int main(int argc, char** argv) {
    @autoreleasepool { return UIApplicationMain(argc,argv,nil,NSStringFromClass(G1AppDelegate.class)); }
}
