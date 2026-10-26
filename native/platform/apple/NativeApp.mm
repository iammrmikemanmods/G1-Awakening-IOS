#import <UIKit/UIKit.h>
#import <MetalKit/MetalKit.h>
#import <QuartzCore/QuartzCore.h>
#import <CommonCrypto/CommonDigest.h>
#include <sys/utsname.h>

#include "MetalRenderer.hpp"
#include "g1/SpriteAnimation.hpp"
#include "g1/InitialPresentation.hpp"
#include "g1/GameSession.hpp"
#include "g1/SpritePlacement.hpp"
#include "NativeDialogue.hpp"
#include "NativeBattle.hpp"
#include "AppleAudio.hpp"

#include <algorithm>
#include <cmath>
#include <deque>
#include <limits>
#include <ctime>
#include <utility>

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

NSString* native_text(const std::string& value) {
    NSString* text = [[NSString alloc] initWithBytes:value.data() length:value.size()
                                             encoding:NSUTF8StringEncoding];
    if (!text) throw g1::FormatError("Original localized text is not valid UTF8");
    return text;
}

UIButton* action_button(NSString* title, id target, SEL selector) {
    UIButton* button = [UIButton buttonWithType:UIButtonTypeSystem];
    [button setTitle:title forState:UIControlStateNormal];
    [button setTitleColor:UIColor.whiteColor forState:UIControlStateNormal];
    [button setTitleColor:[UIColor colorWithWhite:0.5 alpha:1] forState:UIControlStateDisabled];
    button.titleLabel.font = [UIFont systemFontOfSize:13 weight:UIFontWeightSemibold];
    button.backgroundColor = [UIColor colorWithWhite:0.12 alpha:0.92];
    button.layer.cornerRadius = 7;
    [button addTarget:target action:selector forControlEvents:UIControlEventTouchUpInside];
    [button.widthAnchor constraintGreaterThanOrEqualToConstant:82].active = YES;
    [button.heightAnchor constraintEqualToConstant:40].active = YES;
    return button;
}

g1::Matrix4 unit_model(const g1::WorldBootstrap& world, const g1::MovementUnitState& unit) {
    bool on_site = false, in_group = false;
    const auto matches = [&](g1::WorldCoordinate p) {
        return p.x < 128 && p.y < 128 && p.x == unit.tile_x && p.y == unit.tile_y;
    };
    for (const auto& site : world.sites) {
        on_site = on_site || matches(site.position);
        for (const auto& group : site.coordinate_groups)
            in_group = in_group || std::any_of(group.begin(),group.end(),matches);
    }
    return g1::make_unit_sprite_placement({unit.tile_x,unit.tile_y,unit.form,
        unit.offset_x,unit.offset_y,on_site,in_group}).model;
}

bool inside_triangle(CGPoint p, CGPoint a, CGPoint b, CGPoint c) {
    const auto side = [](CGPoint x, CGPoint y, CGPoint z) {
        return (x.x-z.x)*(y.y-z.y)-(y.x-z.x)*(x.y-z.y);
    };
    const double d1=side(p,a,b),d2=side(p,b,c),d3=side(p,c,a);
    return !((d1 < -0.01 || d2 < -0.01 || d3 < -0.01) &&
             (d1 > 0.01 || d2 > 0.01 || d3 > 0.01));
}

struct NativeCameraPan {
    std::size_t command{};
    float from_x{}, from_z{}, to_x{}, to_z{};
    std::uint32_t elapsed{}, duration{360};
    bool reached{};
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
    UIButton* _moveButton;
    UIButton* _captureButton;
    UIButton* _transformButton;
    UIButton* _attackButton;
    UIButton* _battleDoneButton;
    UIButton* _backButton;
    UIButton* _nextButton;
    UIButton* _skipButton;
    UIStackView* _commands;
    UIView* _dialoguePanel;
    UILabel* _dialogueHeading;
    G1DialogueCanvas* _dialogueCanvas;
    UIView* _battlePanel;
    G1BattleCanvas* _battleCanvas;
    G1AppleAudio* _audio;
    std::unique_ptr<g1::MetalRenderer> _renderer;
    std::unique_ptr<g1::FirstMissionScene> _scene;
    std::unique_ptr<g1::GameSession> _session;
    std::unique_ptr<g1::TextTable> _text;
    std::shared_ptr<g1::MetalMesh> _terrain, _range, _cursor, _attackRange;
    std::vector<std::vector<std::vector<g1::SceneVertex>>> _spriteVertices;
    std::vector<std::vector<std::shared_ptr<g1::MetalMesh>>> _spriteMeshes;
    std::vector<g1::SpriteAnimation> _animations;
    std::vector<std::int32_t> _animationIds;
    std::vector<g1::MovementUnitState> _previousUnits;
    std::vector<std::pair<std::size_t,g1::CompletionPresentation>> _pendingCompletionRequests;
    std::vector<g1::SessionBattle> _completedBattles;
    std::vector<std::size_t> _attackTargets;
    g1::UnitAnimationTable _animationTable;
    std::vector<g1::Matrix4> _unitModels;
    g1::SimulationClock _simulationClock;
    std::optional<NativeCameraPan> _cameraPan;
    std::optional<g1::WorldCoordinate> _pendingDestination;
    std::optional<g1::MovementRange> _previewRange;
    std::optional<std::size_t> _lastSelection;
    InspectionCamera _camera;
    FrameStats _frameStats;
    double _clockOrigin, _lastHudTime;
    std::uint32_t _lastTick;
    std::uint32_t _inputEdges, _randomSeed;
    std::size_t _inputCommand, _dialogueCommand;
    std::uint64_t _simulationTicks, _contentGeneration, _presentedContentChanges;
    std::uint64_t _lastPresentedContent, _cameraReports, _moveActions, _captureActions, _transformActions;
    std::uint64_t _audioRequests, _clampedClockIntervals;
    std::uint64_t _attackActions, _battlePresentationTicks, _battleAcknowledgements;
    std::uint8_t _lastMissionMode;
    bool _clockStarted, _loaded, _failed, _moveMode, _attackMode, _rangeDirty;
    NSString* _failure;
    NSString* _notice;
    double _noticeUntil;
}

- (BOOL)prefersStatusBarHidden { return YES; }
- (UIInterfaceOrientationMask)supportedInterfaceOrientations { return UIInterfaceOrientationMaskLandscape; }

- (void)viewDidLoad {
    [super viewDidLoad];
    _dialogueCommand = std::numeric_limits<std::size_t>::max();
    _lastMissionMode = 255;
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
    _title.text = @"G1 Awakening";
    _title.font = [UIFont systemFontOfSize:17 weight:UIFontWeightSemibold];
    _title.textColor = UIColor.whiteColor;
    _hint = [UILabel new];
    _hint.text = @"Loading the first mission…";
    _hint.font = [UIFont systemFontOfSize:12 weight:UIFontWeightMedium];
    _hint.textColor = [UIColor colorWithWhite:0.85 alpha:1];
    _hint.numberOfLines = 2;
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
    [_reportButton setTitle:@"Test report" forState:UIControlStateNormal];
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

    _moveButton = action_button(@"Move",self,@selector(beginMove));
    _captureButton = action_button(@"Capture",self,@selector(capture));
    _transformButton = action_button(@"Transform",self,@selector(transformUnit));
    _attackButton = action_button(@"Attack",self,@selector(beginAttack));
    _commands = [[UIStackView alloc] initWithArrangedSubviews:@[_moveButton,_captureButton,_transformButton,_attackButton]];
    _commands.spacing = 8;
    _commands.translatesAutoresizingMaskIntoConstraints = NO;
    [self.view addSubview:_commands];
    _dialoguePanel = [UIView new];
    _dialoguePanel.backgroundColor = [UIColor colorWithRed:0.02 green:0.04 blue:0.07 alpha:0.96];
    _dialoguePanel.layer.cornerRadius = 12;
    _dialoguePanel.layer.borderWidth = 1;
    _dialoguePanel.layer.borderColor = [UIColor colorWithWhite:0.5 alpha:0.5].CGColor;
    _dialoguePanel.translatesAutoresizingMaskIntoConstraints = NO;
    [self.view addSubview:_dialoguePanel];
    _dialogueHeading = [UILabel new];
    _dialogueHeading.font = [UIFont systemFontOfSize:14 weight:UIFontWeightBold];
    _dialogueHeading.textColor = [UIColor colorWithRed:1 green:0.84 blue:0.25 alpha:1];
    _dialogueHeading.translatesAutoresizingMaskIntoConstraints = NO;
    [_dialoguePanel addSubview:_dialogueHeading];
    _dialogueCanvas = [G1DialogueCanvas new];
    _dialogueCanvas.translatesAutoresizingMaskIntoConstraints = NO;
    [_dialoguePanel addSubview:_dialogueCanvas];
    _backButton = action_button(@"Back",self,@selector(dialogueBack));
    _nextButton = action_button(@"Continue",self,@selector(dialogueNext));
    _skipButton = action_button(@"Skip dialogue",self,@selector(dialogueSkip));
    UIStackView* dialogueButtons = [[UIStackView alloc] initWithArrangedSubviews:@[_backButton,_nextButton,_skipButton]];
    dialogueButtons.spacing = 10;
    dialogueButtons.translatesAutoresizingMaskIntoConstraints = NO;
    [_dialoguePanel addSubview:dialogueButtons];
    [NSLayoutConstraint activateConstraints:@[
        [_commands.trailingAnchor constraintEqualToAnchor:safe.trailingAnchor constant:-16],
        [_commands.bottomAnchor constraintEqualToAnchor:safe.bottomAnchor constant:-42],
        [_dialoguePanel.leadingAnchor constraintEqualToAnchor:safe.leadingAnchor constant:16],
        [_dialoguePanel.trailingAnchor constraintEqualToAnchor:safe.trailingAnchor constant:-16],
        [_dialoguePanel.bottomAnchor constraintEqualToAnchor:safe.bottomAnchor constant:-40],
        [_dialoguePanel.heightAnchor constraintEqualToConstant:174],
        [_dialogueHeading.leadingAnchor constraintEqualToAnchor:_dialoguePanel.leadingAnchor constant:14],
        [_dialogueHeading.trailingAnchor constraintEqualToAnchor:_dialoguePanel.trailingAnchor constant:-14],
        [_dialogueHeading.topAnchor constraintEqualToAnchor:_dialoguePanel.topAnchor constant:10],
        [_dialogueCanvas.leadingAnchor constraintEqualToAnchor:_dialoguePanel.leadingAnchor constant:14],
        [_dialogueCanvas.trailingAnchor constraintEqualToAnchor:_dialoguePanel.trailingAnchor constant:-14],
        [_dialogueCanvas.topAnchor constraintEqualToAnchor:_dialogueHeading.bottomAnchor constant:6],
        [_dialogueCanvas.bottomAnchor constraintEqualToAnchor:dialogueButtons.topAnchor constant:-8],
        [dialogueButtons.trailingAnchor constraintEqualToAnchor:_dialoguePanel.trailingAnchor constant:-12],
        [dialogueButtons.bottomAnchor constraintEqualToAnchor:_dialoguePanel.bottomAnchor constant:-10]]];
    _dialoguePanel.hidden = YES;
    _commands.hidden = YES;

    _battlePanel = [UIView new];
    _battlePanel.backgroundColor = [UIColor colorWithRed:0.025 green:0.04 blue:0.065 alpha:0.97];
    _battlePanel.layer.cornerRadius = 14;
    _battlePanel.layer.borderWidth = 1;
    _battlePanel.layer.borderColor = [UIColor colorWithWhite:0.5 alpha:0.6].CGColor;
    _battlePanel.translatesAutoresizingMaskIntoConstraints = NO;
    [self.view addSubview:_battlePanel];
    _battleCanvas = [G1BattleCanvas new];
    _battleCanvas.translatesAutoresizingMaskIntoConstraints = NO;
    [_battlePanel addSubview:_battleCanvas];
    _battleDoneButton = action_button(@"Continue",self,@selector(finishBattle));
    _battleDoneButton.translatesAutoresizingMaskIntoConstraints = NO;
    [_battlePanel addSubview:_battleDoneButton];
    [NSLayoutConstraint activateConstraints:@[
        [_battlePanel.leadingAnchor constraintEqualToAnchor:safe.leadingAnchor constant:22],
        [_battlePanel.trailingAnchor constraintEqualToAnchor:safe.trailingAnchor constant:-22],
        [_battlePanel.centerYAnchor constraintEqualToAnchor:safe.centerYAnchor],
        [_battlePanel.heightAnchor constraintEqualToConstant:234],
        [_battleCanvas.leadingAnchor constraintEqualToAnchor:_battlePanel.leadingAnchor constant:12],
        [_battleCanvas.trailingAnchor constraintEqualToAnchor:_battlePanel.trailingAnchor constant:-12],
        [_battleCanvas.topAnchor constraintEqualToAnchor:_battlePanel.topAnchor constant:12],
        [_battleCanvas.bottomAnchor constraintEqualToAnchor:_battleDoneButton.topAnchor constant:-8],
        [_battleDoneButton.trailingAnchor constraintEqualToAnchor:_battlePanel.trailingAnchor constant:-16],
        [_battleDoneButton.bottomAnchor constraintEqualToAnchor:_battlePanel.bottomAnchor constant:-12]]];
    _battlePanel.hidden = YES;

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
        _text = std::make_unique<g1::TextTable>(g1::load_text_table(archive));
        const auto animationTable = archive.find(309,0xf4e02223U);
        if (animationTable.size() != 1) throw g1::FormatError("Unit animation table is missing");
        _animationTable = g1::decode_unit_animation_table(archive.read(animationTable.front()));
        _randomSeed = static_cast<std::uint32_t>(std::time(nullptr));
        _session = std::make_unique<g1::GameSession>(_scene->world,_randomSeed);
        _audio = [[G1AppleAudio alloc] initWithArchive:archive];
        for (std::int32_t group=0;group<3;++group)
            [_audio request:g1::MissionAudioRequest{0,group}];
        _previousUnits = _session->units();
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
            _animationIds.push_back(static_cast<std::int32_t>(initial.animation));
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
        if (_session->world().camera) {
            _camera.center_x = (_session->world().camera->x + 0.5F) * 0.32F;
            _camera.center_z = (_session->world().camera->y + 0.5F) * 0.32F;
        }
        [self.view layoutIfNeeded];
        [self refreshControls];
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
    _title.text = @"G1 Awakening — test stopped";
    _hint.text = message;
    _hint.textColor = [UIColor colorWithRed:1 green:0.6 blue:0.55 alpha:1];
    _commands.hidden = YES;
    _dialoguePanel.hidden = YES;
    _battlePanel.hidden = YES;
}

- (void)inactive:(NSNotification*)notification {
    (void)notification;
    _metalView.paused = YES;
    _clockStarted = false;
    _simulationClock.reset();
    _inputEdges = 0;
    if (_session) _previousUnits = _session->units();
    _frameStats.times.clear();
    [_audio setForegroundActive:NO];
}

- (void)active:(NSNotification*)notification {
    (void)notification;
    _clockStarted = false;
    _simulationClock.reset();
    if (_session) _previousUnits = _session->units();
    if (_loaded && !_failed) _metalView.paused = NO;
    [_audio setForegroundActive:YES];
}

- (void)resetView {
    if (!_scene) return;
    if (_session && (_session->mission().gate == g1::MissionGate::camera || _session->battle())) return;
    _camera.fit(*_scene,_metalView.bounds.size);
    ++_contentGeneration;
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
    _metalView.preferredFramesPerSecond = MIN(60,screen.maximumFramesPerSecond);
}

- (void)mtkView:(MTKView*)view drawableSizeWillChange:(CGSize)size {
    (void)view;
    if (_scene && size.height > 0) {
        _camera.aspect = static_cast<float>(size.width / size.height);
        ++_contentGeneration;
    }
}

- (void)pan:(UIPanGestureRecognizer*)gesture {
    if (!_loaded || _metalView.bounds.size.height <= 0 || _session->mission().interaction_mode != 0 || _session->battle()) return;
    const CGPoint delta = [gesture translationInView:_metalView];
    const float scale = _camera.span / static_cast<float>(_metalView.bounds.size.height);
    _camera.center_x -= static_cast<float>(delta.x) * scale;
    _camera.center_z += static_cast<float>(delta.y) * scale / InspectionCamera::up_z;
    ++_contentGeneration;
    [gesture setTranslation:CGPointZero inView:_metalView];
}

- (void)pinch:(UIPinchGestureRecognizer*)gesture {
    if (!_loaded || _session->mission().interaction_mode != 0 || _session->battle()) return;
    if (gesture.scale > 0)
        _camera.span = std::clamp(_camera.span / static_cast<float>(gesture.scale),
                                  _camera.base_span * 0.2F, _camera.base_span * 3.0F);
    gesture.scale = 1;
    ++_contentGeneration;
}

- (void)tap:(UITapGestureRecognizer*)gesture {
    if (!_loaded || _failed) return;
    try {
        if (_session->mission().interaction_mode != 0 || _session->moving() || _session->battle()) return;
        const auto point = [gesture locationInView:_metalView];
        const auto size = _metalView.bounds.size;
        if (size.width <= 0 || size.height <= 0) return;
        std::optional<g1::WorldCoordinate> tile;
        float closest = std::numeric_limits<float>::max();
        const auto camera = _camera.matrix();
        for (const auto& quad : _scene->terrain.quads) {
            if (quad.face != g1::TerrainFace::top) continue;
            std::array<CGPoint,4> screen{};
            float depth = 0;
            for (std::size_t i=0;i<4;++i) {
                const auto& p = quad.positions[i];
                const auto clip = transform(camera,{{p[0]*_scene->terrain.position_scale,
                    p[1]*_scene->terrain.position_scale,p[2]*_scene->terrain.position_scale,1}});
                screen[i] = CGPointMake((clip[0]/clip[3]*0.5+0.5)*size.width,
                                          (0.5-clip[1]/clip[3]*0.5)*size.height);
                depth += clip[2]/clip[3];
            }
            if ((inside_triangle(point,screen[0],screen[1],screen[2]) ||
                 inside_triangle(point,screen[2],screen[1],screen[3])) && depth < closest) {
                closest = depth;
                tile = g1::WorldCoordinate{static_cast<std::uint8_t>(quad.tile_x),
                                          static_cast<std::uint8_t>(quad.tile_y)};
            }
        }
        bool occupied = false;
        if (tile) for (const auto& unit : _session->world().units)
            occupied = occupied || (unit.active && unit.x == tile->x && unit.y == tile->y);
        if (_moveMode && tile && !occupied && _previewRange &&
            _previewRange->at(tile->x,tile->y) >= 0 &&
            _previewRange->at(tile->x,tile->y) != g1::movement_reserved_cell) {
            if (_pendingDestination && _pendingDestination->x == tile->x && _pendingDestination->y == tile->y) {
                const auto result = _session->move_selected_to(*tile);
                if (result == g1::MoveRequestResult::started) {
                    ++_moveActions;
                    _moveMode = false;
                    _pendingDestination.reset();
                    _rangeDirty = true;
                    _notice = @"Moving…";
                } else {
                    _notice = @"That move is not available.";
                }
            } else {
                _pendingDestination = tile;
                _rangeDirty = true;
                _notice = @"Tap the same tile again to move.";
            }
            _noticeUntil = CACurrentMediaTime()+3;
            [self refreshControls];
            return;
        }
        NSInteger selected = -1;
        double best = std::numeric_limits<double>::max();
        for (std::size_t i = 0; i < _animations.size(); ++i) {
            const auto unitIndex = _scene->sprites[i].unit_index;
            if (!_session->units().at(unitIndex).active) continue;
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
                if (distance < best) { best = distance; selected = static_cast<NSInteger>(i); }
            }
        }
        if (selected >= 0) {
            const auto index = _scene->sprites[static_cast<std::size_t>(selected)].unit_index;
            if (_attackMode) {
                if (std::find(_attackTargets.begin(),_attackTargets.end(),index) != _attackTargets.end() &&
                    _session->attack_selected(index)) {
                    ++_attackActions;
                    _attackMode = false;
                    _rangeDirty = true;
                    _notice = nil;
                } else {
                    _notice = @"Select a highlighted enemy.";
                    _noticeUntil = CACurrentMediaTime()+3;
                }
                [self refreshControls];
                return;
            }
            if (_session->select(index)) {
                _moveMode = false;
                _attackMode = false;
                _pendingDestination.reset();
                _notice = nil;
                _rangeDirty = true;
            } else {
                _notice = @"Select one of your available units.";
                _noticeUntil = CACurrentMediaTime()+3;
            }
        } else if (!_moveMode && !_attackMode) {
            _session->clear_selection();
            _rangeDirty = true;
        }
        [self refreshControls];
    } catch (const std::exception& error) {
        [self fail:[NSString stringWithUTF8String:error.what()]];
    }
}

- (void)refreshRange {
    if (!_rangeDirty) return;
    _rangeDirty = false;
    _range.reset(); _cursor.reset(); _attackRange.reset();
    _previewRange = _session->selected_movement_range();
    _attackTargets = _session->selected_attack_targets();
    if (!_previewRange) {
        _moveMode = false;
        _pendingDestination.reset();
    }
    if (_attackTargets.empty()) _attackMode = false;
    if (_moveMode && _previewRange) {
        g1::TerrainMesh selected;
        selected.position_scale = _scene->terrain.position_scale;
        g1::TerrainMesh cursor;
        cursor.position_scale = selected.position_scale;
        for (const auto& quad : _scene->terrain.quads)
            if (quad.face == g1::TerrainFace::top && _previewRange->at(quad.tile_x,quad.tile_y) >= 0 &&
                _previewRange->at(quad.tile_x,quad.tile_y) != g1::movement_reserved_cell) {
                bool occupied = false;
                for (const auto& unit : _session->world().units)
                    occupied = occupied || (unit.active && unit.x == quad.tile_x && unit.y == quad.tile_y);
                if (!occupied) selected.quads.push_back(quad);
                if (!occupied && _pendingDestination && _pendingDestination->x == quad.tile_x &&
                    _pendingDestination->y == quad.tile_y) cursor.quads.push_back(quad);
            }
        auto vertices = g1::terrain_vertices(selected);
        for (auto& vertex : vertices) { vertex.position[1] += 0.003F; vertex.uv = {{0,0}}; }
        if (!vertices.empty()) _range = _renderer->mesh(vertices);
        vertices = g1::terrain_vertices(cursor);
        for (auto& vertex : vertices) { vertex.position[1] += 0.006F; vertex.uv = {{0,0}}; }
        if (!vertices.empty()) _cursor = _renderer->mesh(vertices);
    }
    if (_attackMode) {
        g1::TerrainMesh targets;
        targets.position_scale = _scene->terrain.position_scale;
        for (const auto& quad : _scene->terrain.quads) if (quad.face == g1::TerrainFace::top)
            for (const auto index : _attackTargets) {
                const auto& unit = _session->units().at(index);
                if (unit.tile_x == quad.tile_x && unit.tile_y == quad.tile_y) {
                    targets.quads.push_back(quad);
                    break;
                }
            }
        auto vertices = g1::terrain_vertices(targets);
        for (auto& vertex : vertices) { vertex.position[1] += 0.006F; vertex.uv = {{0,0}}; }
        if (!vertices.empty()) _attackRange = _renderer->mesh(vertices);
    }
    ++_contentGeneration;
}

- (void)refreshControls {
    if (!_session || _failed) return;
    if (_lastMissionMode != _session->mission().interaction_mode) {
        _lastMissionMode = _session->mission().interaction_mode;
        _moveMode = false; _attackMode = false;
        _pendingDestination.reset(); _rangeDirty = true;
    }
    if (_lastSelection != _session->selected()) {
        _lastSelection = _session->selected();
        _rangeDirty = true;
        _pendingDestination.reset();
        _moveMode = false;
        _attackMode = false;
    }
    [self refreshRange];
    const auto& mission = _session->mission();
    const bool battle = _session->battle().has_value();
    _battlePanel.hidden = !battle;
    if (battle) {
        const auto& exchange = *_session->battle();
        const auto name = [&](const g1::CombatUnitState& unit) {
            const auto& definition = _session->world().unit_definitions.at(unit.type);
            return native_text(_text->at(g1::script_text_id(g1::unit_text_index(definition.raw_text_indices.at(unit.form)))));
        };
        [_battleCanvas showBattle:exchange attacker:name(exchange.attacker_before) defender:name(exchange.defender_before)];
        _battleDoneButton.enabled = [_battleCanvas readyForAcknowledgement];
    }
    const bool dialogue = mission.gate == g1::MissionGate::dialogue && mission.dialogue.has_value();
    _dialoguePanel.hidden = !dialogue || battle;
    _commands.hidden = battle || dialogue || mission.interaction_mode != 0 || !_session->selected() || _session->moving();
    if (battle) {
        _hint.text = @"Battle";
    } else if (dialogue) {
        if (_dialogueCommand != mission.command_index) {
            _dialogueCommand = mission.command_index;
            _dialogueHeading.text = native_text(_text->at(mission.dialogue->heading_text_id));
            [_dialogueCanvas setOriginalText:native_text(_text->at(mission.dialogue->text_id))];
            _inputEdges = 0;
        }
        [_dialogueCanvas showProgress:mission.dialogue->progress];
        _backButton.enabled = mission.dialogue->progress.first_line > 0;
        _hint.text = @"";
    } else if (mission.stop != g1::MissionStop::none) {
        _hint.text = @"The next part of this campaign is not available in this build. Details are in the test report.";
        _commands.hidden = YES;
    } else if (_notice && CACurrentMediaTime() < _noticeUntil) {
        _hint.text = _notice;
    } else if (_session->moving()) {
        _hint.text = @"Moving…";
    } else if (_session->selected()) {
        const auto index = *_session->selected();
        const auto& unit = _session->world().units.at(index);
        const auto& definition = _session->world().unit_definitions.at(unit.type);
        const auto& combat = _session->combat_units().at(index);
        const auto name = native_text(_text->at(g1::script_text_id(g1::unit_text_index(definition.raw_text_indices.at(unit.form)))));
        _hint.text = _attackMode ? @"Select a highlighted enemy to attack." : _moveMode ? @"Tap a green tile, then tap it again to move." :
            [NSString stringWithFormat:@"%@ · HP %u · ATK %d–%d · DEF %d",name,unsigned(combat.health),
                int(combat.stats.attack_low),int(combat.stats.attack_high),int(combat.stats.defense)];
    } else if (mission.objective) {
        _hint.text = native_text(_text->at(mission.objective->text_id));
    } else {
        _hint.text = @"Select a unit. Drag or pinch to move the view.";
    }
    _moveButton.enabled = _previewRange && _previewRange->has_unoccupied_destination && !_session->moving();
    _captureButton.enabled = _session->selected_can_capture();
    _transformButton.enabled = _session->selected_transform_eligibility() == g1::TransformEligibility::allowed;
    _attackButton.enabled = !_attackTargets.empty() && !battle;
    if (_session->world().title_text_index)
        _title.text = native_text(_text->at(g1::script_text_id(*_session->world().title_text_index)));
}

- (void)beginMove {
    if (!_loaded || _failed) return;
    try {
        _moveMode = true;
        _attackMode = false;
        _pendingDestination.reset();
        _rangeDirty = true;
        _notice = nil;
        [self refreshControls];
    } catch (const std::exception& e) { [self fail:native_text(e.what())]; }
}

- (void)beginAttack {
    if (!_loaded || _failed || _session->battle()) return;
    try {
        _attackMode = !_session->selected_attack_targets().empty();
        _moveMode = false;
        _pendingDestination.reset();
        _rangeDirty = true;
        _notice = nil;
        [self refreshControls];
    } catch (const std::exception& e) { [self fail:native_text(e.what())]; }
}

- (void)finishBattle {
    if (!_loaded || _failed || !_session->battle() || ![_battleCanvas readyForAcknowledgement]) return;
    try {
        const auto battle = *_session->battle();
        if (battle.token != [_battleCanvas battleToken]) return;
        // This user action is enabled only after the final native result view
        // has actually drawn. Elapsed time alone never acknowledges a battle.
        _session->report_battle_finished(battle.token);
        _completedBattles.push_back(battle);
        if (_completedBattles.size() > 64) _completedBattles.erase(_completedBattles.begin());
        ++_battleAcknowledgements;
        _rangeDirty = true;
        _attackMode = false;
        _notice = nil;
        [self refreshControls];
    } catch (const std::exception& e) { [self fail:native_text(e.what())]; }
}

- (void)capture {
    if (!_loaded || _failed) return;
    try {
        const auto result = _session->capture_selected();
        if (result.status == g1::CaptureStatus::captured) {
            ++_captureActions;
            if (result.audio_5_12) [self dispatchAudio:g1::MissionAudioRequest{5,12}];
            _notice = @"Captured.";
            _noticeUntil = CACurrentMediaTime()+2;
            _rangeDirty = true;
            _pendingDestination.reset();
            _moveMode = false;
            _attackMode = false;
            ++_contentGeneration;
        } else if (result.message_id) {
            UIAlertController* alert = [UIAlertController alertControllerWithTitle:@"Capture"
                message:native_text(_text->at(*result.message_id)) preferredStyle:UIAlertControllerStyleAlert];
            [alert addAction:[UIAlertAction actionWithTitle:@"OK" style:UIAlertActionStyleDefault handler:nil]];
            [self presentViewController:alert animated:YES completion:nil];
        }
        [self refreshControls];
    } catch (const std::exception& e) { [self fail:native_text(e.what())]; }
}

- (void)transformUnit {
    if (!_loaded || _failed) return;
    try {
        const auto result = _session->transform_selected();
        if (result) {
            ++_transformActions;
            if (result->audio_event_in_group5)
                [self dispatchAudio:g1::MissionAudioRequest{5,*result->audio_event_in_group5}];
            _rangeDirty = true;
            _pendingDestination.reset();
            _moveMode = false;
            _attackMode = false;
            _notice = nil;
        }
        [self refreshControls];
    } catch (const std::exception& e) { [self fail:native_text(e.what())]; }
}

- (void)queueDialogueEdge:(std::uint32_t)edge {
    if (!_loaded || _failed || _session->mission().gate != g1::MissionGate::dialogue) return;
    _inputCommand = _session->mission().command_index;
    _inputEdges |= edge;
}
- (void)dialogueBack { [self queueDialogueEdge:1]; }
- (void)dialogueNext { [self queueDialogueEdge:16]; }
- (void)dialogueSkip { [self queueDialogueEdge:128]; }

- (void)dispatchAudio:(g1::MissionAudioRequest)request {
    ++_audioRequests;
    // The return value is the original query/operation result, not generic
    // output success. Actual framework/cache failures are in diagnostics.
    [_audio request:request];
}

- (void)advanceCamera:(std::uint32_t)delta {
    const auto& mission = _session->mission();
    if (mission.gate != g1::MissionGate::camera || !mission.camera) return;
    if (!_cameraPan || _cameraPan->command != mission.command_index) {
        const auto& request = *mission.camera;
        if (request.x < 0 || request.y < 0 || request.x >= _session->world().grid.width ||
            request.y >= _session->world().grid.height)
            throw g1::FormatError("Camera request lies outside the recovered scene");
        _cameraPan = NativeCameraPan{mission.command_index,_camera.center_x,_camera.center_z,
            (request.x+0.5F)*0.32F,(request.y+0.5F)*0.32F,0,request.immediate ? 0U : 360U,false};
    }
    auto& pan = *_cameraPan;
    if (pan.reached) return;
    pan.elapsed = std::min(pan.elapsed+delta,pan.duration);
    const float t = pan.duration ? static_cast<float>(pan.elapsed)/pan.duration : 1.0F;
    const float smooth = t*t*(3-2*t);
    _camera.center_x = pan.from_x+(pan.to_x-pan.from_x)*smooth;
    _camera.center_z = pan.from_z+(pan.to_z-pan.from_z)*smooth;
    pan.reached = pan.elapsed == pan.duration;
    ++_contentGeneration;
}

- (void)advanceSprites:(std::uint32_t)delta {
    std::vector<std::size_t> order;
    for (std::size_t i=0;i<_scene->sprites.size();++i) order.push_back(i);
    std::sort(order.begin(),order.end(),[&](std::size_t a,std::size_t b) {
        return _session->world().units[_scene->sprites[a].unit_index].type <
               _session->world().units[_scene->sprites[b].unit_index].type;
    });
    // Original6cd20 stores one shared delta for the entire ascending-type loop.
    auto sharedDelta = delta;
    for (const auto i : order) {
        const auto index = _scene->sprites[i].unit_index;
        const auto& unit = _session->units().at(index);
        const auto& worldUnit = _session->world().units.at(index);
        if (!unit.active) continue;
        const auto& row = _animationTable.at(worldUnit.type);
        const auto signedId = [](std::uint8_t value) { return value < 128 ? int(value) : int(value)-256; };
        const int special = signedId(row[8]);
        bool reverse = false;
        std::int32_t repeats = -1;
        int desired;
        if (_session->transform_animation_pending(index)) {
            desired = special;
            reverse = unit.form == 0;
            repeats = 1;
            _session->clear_transform_animation_request(index); // Original6cdc6.
        } else {
            if (unit.form > 1 || unit.facing > 3) throw g1::FormatError("Unsupported sprite form/facing");
            desired = signedId(row[unit.form*4+unit.facing]);
        }
        const auto beforeFrame = _animations[i].current_frame();
        bool changed = false;
        if (_animationIds[i] == special && !_animations[i].state().completed) {
            if (sharedDelta > std::uint32_t(std::numeric_limits<std::int32_t>::max()/2))
                throw g1::FormatError("Original shared sprite delta exceeded signed range");
            sharedDelta *= 2;
        } else if (desired != _animationIds[i] && desired != -1) {
            if (desired < 0 || static_cast<std::size_t>(desired) >= _scene->sprites[i].descriptor.animations().size())
                throw g1::FormatError("Sprite animation request exceeds recovered descriptor");
            _animations[i] = g1::SpriteAnimation(_scene->sprites[i].descriptor.animations()[desired],repeats,reverse);
            _animationIds[i] = desired;
            changed = true; // Original new sequence is not advanced in this tick.
        }
        if (!changed) {
            if (unit.flag_2c && worldUnit.owner == _session->current_player() && _animationIds[i] != special)
                _animations[i].select_step(0);
            else _animations[i].advance_ms(sharedDelta);
        }
        if (changed || beforeFrame != _animations[i].current_frame()) ++_contentGeneration;
    }
}

- (void)simulate:(std::uint32_t)delta {
    const auto steps = _simulationClock.add_elapsed(delta);
    for (std::uint32_t n=0;n<steps;++n) {
        _previousUnits = _session->units();
        [self advanceCamera:g1::SimulationClock::step_ms];
        [self refreshControls];
        if (_session->battle()) {
            [_battleCanvas advance:g1::SimulationClock::step_ms];
            ++_battlePresentationTicks;
            [self advanceSprites:g1::SimulationClock::step_ms];
            continue;
        }
        g1::MissionTickInput input;
        if (_session->mission().gate == g1::MissionGate::dialogue) {
            input.dialogue_layout = [_dialogueCanvas layoutFeedback];
            if (input.dialogue_layout->box_height <= 0 || input.dialogue_layout->line_height <= 0)
                continue; // No simulation/dialogue completion before real native layout.
            if (_inputCommand == _session->mission().command_index) input.input_edges = _inputEdges;
        } else _inputEdges = 0;
        const auto result = _session->tick(g1::SimulationClock::step_ms,input);
        _inputEdges = result.mission.remaining_input_edges;
        for (const auto effect : result.mission.effects)
            if (effect == g1::MissionEffect::skip_dialogue_audio_event)
                [self dispatchAudio:g1::MissionAudioRequest{5,18}];
        if (result.completion) {
            for (const auto request : result.completion->audio_requests) [self dispatchAudio:request];
            _pendingCompletionRequests.emplace_back(_session->mission().command_index,*result.completion);
        }
        ++_simulationTicks;
        if (result.movement_finished || result.world_changed) _rangeDirty = true;
        [self advanceSprites:g1::SimulationClock::step_ms];
    }
    [self advanceCamera:0];
    [self refreshControls];
    const float blend = _simulationClock.interpolation();
    for (std::size_t i=0;i<_unitModels.size();++i) {
        const auto index = _scene->sprites[i].unit_index;
        const auto& unit = _session->units().at(index);
        auto model = unit_model(_session->world(),unit);
        if (index < _previousUnits.size() && _previousUnits[index].form == unit.form) {
            const auto previous = unit_model(_session->world(),_previousUnits[index]);
            for (std::size_t j=12;j<15;++j) model[j] = previous[j]+(model[j]-previous[j])*blend;
        }
        if (model != _unitModels[i]) { _unitModels[i] = model; ++_contentGeneration; }
    }
}

- (void)recordPresentation:(double)time content:(std::uint64_t)content camera:(NSInteger)cameraToken {
    if (_metalView.paused || time <= 0 || !std::isfinite(time)) return;
    if (!_frameStats.times.empty() && time <= _frameStats.times.back()) return;
    _frameStats.add(time);
    if (content != _lastPresentedContent) { ++_presentedContentChanges; _lastPresentedContent = content; }
    if (cameraToken >= 0 && _session && _session->mission().gate == g1::MissionGate::camera &&
        _session->mission().command_index == static_cast<std::size_t>(cameraToken)) {
        try {
            _session->report_camera(static_cast<std::size_t>(cameraToken),true);
            ++_cameraReports;
        } catch (const std::exception& e) { [self fail:native_text(e.what())]; }
    }
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
            if (std::uint32_t(tick - _lastTick) > 1000U) ++_clampedClockIntervals;
            _lastTick = tick;
            [self simulate:delta];
            const auto camera = _camera.matrix();
            std::vector<g1::MetalDraw> draws{
                {_terrain,_textures[@(_scene->terrain.atlas_resource_id)],camera,{{1,1,1,1}},true}};
            if (_range) draws.push_back({_range,_white,camera,{{0.12F,0.9F,0.85F,0.36F}},false});
            if (_cursor) draws.push_back({_cursor,_white,camera,{{1,0.82F,0.12F,0.6F}},false});
            if (_attackRange) draws.push_back({_attackRange,_white,camera,{{1,0.18F,0.14F,0.48F}},false});
            std::vector<std::size_t> order;
            for (std::size_t i = 0; i < _animations.size(); ++i)
                if (_session->units().at(_scene->sprites[i].unit_index).active) order.push_back(i);
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
            const std::uint64_t content = _contentGeneration;
            const NSInteger cameraToken = _cameraPan && _cameraPan->reached &&
                _session->mission().gate == g1::MissionGate::camera ?
                static_cast<NSInteger>(_cameraPan->command) : -1;
            [drawable addPresentedHandler:^(id<MTLDrawable> presented) {
                const double time = presented.presentedTime;
                dispatch_async(dispatch_get_main_queue(),^{ [weakSelf recordPresentation:time content:content camera:cameraToken]; });
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
    NSMutableArray* unitState = [NSMutableArray new];
    NSMutableArray* siteState = [NSMutableArray new];
    NSMutableArray* completionRequests = [NSMutableArray new];
    NSMutableArray* battleHistory = [NSMutableArray new];
    const auto battleJson = [](const g1::SessionBattle& battle) -> NSDictionary* {
        const auto strikeJson = [](const g1::CombatStrike& strike) -> NSDictionary* {
            return @{@"rolled_damage":@(strike.rolled_damage),@"health_before":@(strike.health_before),
                @"health_after":@(strike.health_after),@"evaded":@(strike.evaded),@"immune":@(strike.immune),
                @"random_words":@(strike.random_words)};
        };
        NSMutableArray* destroyed = [NSMutableArray new];
        for (const auto& unit : battle.exchange.destroyed)
            [destroyed addObject:@{@"type":@(unit.type),@"owner":@(unit.owner),@"x":@(unit.x),@"y":@(unit.y)}];
        NSMutableArray* support = [NSMutableArray new];
        for (const auto type : battle.exchange.support_types) [support addObject:@(type)];
        return @{@"token":@(battle.token),@"attacker_index":@(battle.attacker),@"defender_index":@(battle.defender),
            @"attacker_type":@(battle.attacker_before.type),@"defender_type":@(battle.defender_before.type),
            @"attacker_health_before":@(battle.attacker_before.health),@"defender_health_before":@(battle.defender_before.health),
            @"attack":strikeJson(battle.exchange.attack),
            @"counterattack":battle.exchange.counterattack ? strikeJson(*battle.exchange.counterattack) : NSNull.null,
            @"destroyed":destroyed,@"support_types":support,@"random_words":@(battle.exchange.random_words)};
    };
    for (const auto& battle : _completedBattles) [battleHistory addObject:battleJson(battle)];
    for (const auto& entry : _pendingCompletionRequests) {
        NSMutableArray* audio = [NSMutableArray new];
        for (const auto& request : entry.second.audio_requests)
            [audio addObject:@{@"operation":@(request.operation),@"argument":@(request.argument)}];
        [completionRequests addObject:@{@"command_index":@(entry.first),@"audio":audio,
            @"text_resource_id":entry.second.text_resource_id ? @(*entry.second.text_resource_id) : NSNull.null,
            @"audio_requests_forwarded_to_host":@(_audio != nil),@"text_presentation_performed":@NO}];
    }
    if (_session) {
        for (std::size_t i=0;i<_session->units().size();++i) {
            const auto& unit = _session->units()[i];
            const auto& world = _session->world().units[i];
            const auto& combat = _session->combat_units()[i];
            [unitState addObject:@{@"type":@(world.type),@"owner":@(world.owner),@"form":@(unit.form),
                @"active":@(unit.active),@"x":@(unit.tile_x),@"y":@(unit.tile_y),
                @"offset_x":@(unit.offset_x),@"offset_y":@(unit.offset_y),@"facing":@(unit.facing),
                @"spent_movement":@(unit.spent_budget),@"action_used_flag2c":@(unit.flag_2c),
                @"transformed_flag2d":@(unit.flag_2d),@"health":@(combat.health)}];
        }
        for (const auto& site : _session->sites()) {
            NSMutableArray* groups = [NSMutableArray new];
            for (const auto& group : site.item_states) {
                NSMutableArray* items = [NSMutableArray new];
                for (const auto owner : group) [items addObject:@(owner)];
                [groups addObject:items];
            }
            [siteState addObject:@{@"site_owner":@(site.state),@"item_owners":groups}];
        }
    }
    NSDictionary* report = @{
        @"artifact_kind": @"native first-mission gameplay test", @"source_commit": info[@"G1SourceCommit"] ?: @"unknown",
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
        @"camera": @"Native inspection projection; real tile-focus requests with 360 ms native pan; original camera fidelity unverified",
        @"camera_requests_acknowledged_after_presentation": @(_cameraReports),
        @"campaign_cursor": @(_session ? _session->mission().command_index : 0),
        @"mission_gate": @(_session ? static_cast<int>(_session->mission().gate) : -1),
        @"mission_stop_detail": _session ? native_text(_session->mission().stop_detail) : @"not loaded",
        @"current_player": @(_session ? _session->current_player() : 0),
        @"simulation_step_ms": @(g1::SimulationClock::step_ms),
        @"simulation_ticks_total": @(_simulationTicks),
        @"clock_clamp_intervals_over1000ms": @(_clampedClockIntervals),
        @"movement_interpolation": @"Previous/current exact model translation; no extra simulation steps at display rate",
        @"presented_content_generation_changes": @(_presentedContentChanges),
        @"content_change_scope": @"Scene state/mesh generation changes; not a framebuffer pixel comparison or 60 Hz animation claim",
        @"dialogue_layout": @"Native TextKit line fragments and glyph drawing; original text/headings, native font metrics",
        @"dialogue_drawn_revision": @([_dialogueCanvas drawnRevision]),
        @"dialogue_input_masks": @[@1,@16,@128],
        @"move_actions_started": @(_moveActions),
        @"capture_actions_completed": @(_captureActions),
        @"transform_actions_started": @(_transformActions),
        @"attack_actions_started": @(_attackActions),
        @"battle_presentations_acknowledged": @(_battleAcknowledgements),
        @"battle_presentation_ticks": @(_battlePresentationTicks),
        @"battle_history":battleHistory,
        @"battle_pending":_session && _session->battle() ? battleJson(*_session->battle()) : NSNull.null,
        @"last_battle_final_view_drawn":@([_battleCanvas readyForAcknowledgement]),
        @"battle_presentation":@"Native before/result HP panel; final view must draw and user Continue must match token; original 3D cinematic parity is not implemented",
        @"audio_game_requests_observed": @(_audioRequests), @"audio_playback_implemented": @YES,
        @"audio_host":_audio ? [_audio diagnostics] : @{@"operational":@NO,@"error":@"Audio host was not created"},
        @"completion_presentation_requests":completionRequests,
        @"random_seed": @(_randomSeed), @"units":unitState, @"sites":siteState,
        @"full_gameplay_implemented": @NO, @"full_campaign_verified": @NO,
        @"native_save_reload_verified": @NO,
        @"remaining_scope": @"Original camera/font/UI and battle-cinematic fidelity, site visual updates, full sound-event coverage and device audio, complete AI/campaign/save flow and XR validation remain unfinished",
        @"measurement_scope": @"Positive monotonic Metal presentedTime samples from current native scene; not full-game performance"
    };
    NSError* error = nil;
    NSData* json = [NSJSONSerialization dataWithJSONObject:report
        options:NSJSONWritingPrettyPrinted | NSJSONWritingSortedKeys error:&error];
    NSURL* file = [NSURL fileURLWithPath:[NSTemporaryDirectory()
        stringByAppendingPathComponent:@"G1-Native-Gameplay-Report.json"]];
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
