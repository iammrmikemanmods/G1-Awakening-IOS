#pragma once

#import <UIKit/UIKit.h>
#include "g1/GameSession.hpp"
#include <algorithm>
#include <cmath>

// Native battle-result presentation. Gameplay outcomes come exclusively from
// SessionBattle; this view does not reconstruct the original 3D cinematic.
@interface G1BattleCanvas : UIView
- (void)showBattle:(const g1::SessionBattle&)battle attacker:(NSString*)attacker defender:(NSString*)defender;
- (void)advance:(std::uint32_t)milliseconds;
- (BOOL)readyForAcknowledgement;
- (std::uint64_t)battleToken;
- (std::uint32_t)presentationElapsed;
@end

@implementation G1BattleCanvas {
    std::optional<g1::SessionBattle> _battle;
    NSString* _attackerName;
    NSString* _defenderName;
    std::uint32_t _elapsed, _duration;
    bool _initialDrawn, _finalDrawn;
}

- (instancetype)initWithFrame:(CGRect)frame {
    self = [super initWithFrame:frame];
    if (self) { self.opaque = NO; self.clipsToBounds = YES; self.isAccessibilityElement = YES; }
    return self;
}

- (void)showBattle:(const g1::SessionBattle&)battle attacker:(NSString*)attacker defender:(NSString*)defender {
    if (_battle && _battle->token == battle.token) return;
    _battle = battle;
    _attackerName = [attacker copy]; _defenderName = [defender copy];
    _elapsed = 0;
    _duration = battle.exchange.counterattack ? 2100U : 1500U;
    _initialDrawn = false; _finalDrawn = false;
    [self setNeedsDisplay];
}

- (void)advance:(std::uint32_t)milliseconds {
    // The real initial draw must precede the timed native result animation.
    if (!_battle || !_initialDrawn || _elapsed == _duration) return;
    _elapsed = static_cast<std::uint32_t>(std::min(std::uint64_t(_elapsed)+milliseconds,
                                                 std::uint64_t(_duration)));
    [self setNeedsDisplay];
}

- (BOOL)readyForAcknowledgement { return _battle && _elapsed == _duration && _finalDrawn; }
- (std::uint64_t)battleToken { return _battle ? _battle->token : 0; }
- (std::uint32_t)presentationElapsed { return _elapsed; }

- (void)drawCombatant:(NSString*)name role:(NSString*)role before:(unsigned)before after:(unsigned)after
             progress:(float)progress x:(CGFloat)x width:(CGFloat)width color:(UIColor*)color {
    [role drawInRect:CGRectMake(x,6,width,18) withAttributes:@{
        NSFontAttributeName:[UIFont systemFontOfSize:11 weight:UIFontWeightMedium],
        NSForegroundColorAttributeName:[UIColor colorWithWhite:0.7 alpha:1]}];
    [name drawInRect:CGRectMake(x,27,width,24) withAttributes:@{
        NSFontAttributeName:[UIFont systemFontOfSize:18 weight:UIFontWeightBold],
        NSForegroundColorAttributeName:UIColor.whiteColor}];
    const float health = float(before)+(float(after)-float(before))*progress;
    const CGRect track = CGRectMake(x,62,width,14);
    [[UIColor colorWithWhite:0.16 alpha:1] setFill];
    [[UIBezierPath bezierPathWithRoundedRect:track cornerRadius:4] fill];
    CGRect fill = track;
    fill.size.width *= std::clamp(health/100.0F,0.0F,1.0F);
    [color setFill];
    [[UIBezierPath bezierPathWithRoundedRect:fill cornerRadius:4] fill];
    NSString* label = progress >= 1 ? [NSString stringWithFormat:@"HP %u → %u",before,after] :
        [NSString stringWithFormat:@"HP %u",static_cast<unsigned>(std::lround(health))];
    [label drawInRect:CGRectMake(x,86,width,24) withAttributes:@{
        NSFontAttributeName:[UIFont monospacedDigitSystemFontOfSize:17 weight:UIFontWeightSemibold],
        NSForegroundColorAttributeName:UIColor.whiteColor}];
}

- (void)drawRect:(CGRect)rect {
    (void)rect;
    if (!_battle || self.bounds.size.width <= 0 || self.bounds.size.height <= 0) return;
    const auto& battle = *_battle;
    const auto& attack = battle.exchange.attack;
    const auto& counter = battle.exchange.counterattack;
    const float attackProgress = std::clamp((float(_elapsed)-400.0F)/600.0F,0.0F,1.0F);
    const float counterProgress = counter ? std::clamp((float(_elapsed)-1250.0F)/600.0F,0.0F,1.0F) : 1.0F;
    const unsigned attackerAfter = counter ? counter->health_after : battle.attacker_before.health;
    const CGFloat width = (self.bounds.size.width-40)/2;
    [self drawCombatant:_attackerName role:@"ATTACKER" before:battle.attacker_before.health
        after:attackerAfter progress:counterProgress x:8 width:width
        color:[UIColor colorWithRed:0.18 green:0.83 blue:0.75 alpha:1]];
    [self drawCombatant:_defenderName role:@"DEFENDER" before:battle.defender_before.health
        after:attack.health_after progress:attackProgress x:width+32 width:width
        color:[UIColor colorWithRed:0.91 green:0.42 blue:0.39 alpha:1]];
    NSString* attackText = attack.evaded ? @"Attack evaded" : attack.immune ? @"Attack: no HP lost (immune)" :
        [NSString stringWithFormat:@"Attack: %+d HP",int(attack.health_after)-int(attack.health_before)];
    NSString* counterText = counter ? (counter->evaded ? @"Counterattack evaded" :
        counter->immune ? @"Counterattack: no HP lost (immune)" :
        [NSString stringWithFormat:@"Counterattack: %+d HP",int(counter->health_after)-int(counter->health_before)]) :
        @"No counterattack";
    NSString* status = _elapsed < 1000 ? @"Attack" : _elapsed < 1850 && counter ? attackText :
        [NSString stringWithFormat:@"%@ · %@",attackText,counterText];
    [status drawInRect:CGRectMake(8,123,self.bounds.size.width-16,38) withAttributes:@{
        NSFontAttributeName:[UIFont systemFontOfSize:13 weight:UIFontWeightMedium],
        NSForegroundColorAttributeName:[UIColor colorWithWhite:0.88 alpha:1]}];
    if (_elapsed == 0) _initialDrawn = true;
    if (_elapsed == _duration) {
        _finalDrawn = true;
        self.accessibilityLabel = [NSString stringWithFormat:@"%@ HP %u to %u. %@ HP %u to %u. %@.",
            _attackerName,unsigned(battle.attacker_before.health),attackerAfter,
            _defenderName,unsigned(battle.defender_before.health),unsigned(attack.health_after),status];
    }
}
@end
