#pragma once

#import <UIKit/UIKit.h>
#include "NativeBitmapFont.hpp"
#include "g1/M3GBattlePresentation.hpp"
#include <algorithm>

// Native point-based HUD over the original animated M3G presentation. Every
// health/damage value comes from the recovered controller; this view has no
// private animation clock, invented HP tween or gameplay acknowledgement.
@interface G1BattleCanvas : UIView
- (void)resetPresentation;
- (void)loadOriginalFonts:(const g1::Archive&)archive;
- (void)showStatus:(const g1::M3GBattleStatus&)status left:(NSString*)left right:(NSString*)right;
- (BOOL)hasDrawnToken:(std::uint64_t)token revision:(std::uint64_t)revision;
@end

@implementation G1BattleCanvas {
    std::optional<g1::M3GBattleStatus> _status;
    NSString* _leftName;
    NSString* _rightName;
    std::uint64_t _drawnToken, _drawnRevision;
    G1BitmapFontFace* _originalNameFont;
}

- (instancetype)initWithFrame:(CGRect)frame {
    self = [super initWithFrame:frame];
    if (self) { self.opaque = NO; self.clipsToBounds = YES; self.isAccessibilityElement = YES; }
    return self;
}

- (void)loadOriginalFonts:(const g1::Archive&)archive {
    _originalNameFont=[[G1BitmapFontFace alloc] initWithArchive:archive slot:2];
    _drawnToken=0; _drawnRevision=0;
    [self setNeedsDisplay];
}

- (void)showStatus:(const g1::M3GBattleStatus&)status left:(NSString*)left right:(NSString*)right {
    if (_status && _status->token == status.token && _status->revision == status.revision) return;
    if (!_status || _status->token != status.token) { _drawnToken = 0; _drawnRevision = 0; }
    _status = status;
    _leftName = [left copy]; _rightName = [right copy];
    [self setNeedsDisplay];
}

- (void)resetPresentation {
    _status.reset(); _leftName = nil; _rightName = nil;
    _drawnToken = 0; _drawnRevision = 0;
    self.accessibilityLabel = @"";
    [self setNeedsDisplay];
}

- (BOOL)hasDrawnToken:(std::uint64_t)token revision:(std::uint64_t)revision {
    return token != 0 && _drawnToken == token && _drawnRevision == revision;
}

- (void)drawCombatant:(NSString*)name health:(std::int32_t)health x:(CGFloat)x
                 width:(CGFloat)width color:(UIColor*)color {
    const CGRect nameRect=CGRectMake(x,1,width-62,21);
    const BOOL useOriginal=_originalNameFont && [_originalNameFont supportsText:name] &&
        [_originalNameFont sizeForText:name height:15].width<=nameRect.size.width &&
        [_originalNameFont sizeForText:name height:15].height<=nameRect.size.height;
    if(useOriginal)
        [_originalNameFont drawText:name rect:nameRect height:15 alignment:NSTextAlignmentLeft];
    else
        [name drawInRect:nameRect withAttributes:@{
            NSFontAttributeName:[UIFont systemFontOfSize:15 weight:UIFontWeightBold],
            NSForegroundColorAttributeName:UIColor.whiteColor}];
    NSString* label = [NSString stringWithFormat:@"HP %d",int(health)];
    [label drawInRect:CGRectMake(x+width-62,2,62,20) withAttributes:@{
        NSFontAttributeName:[UIFont monospacedDigitSystemFontOfSize:14 weight:UIFontWeightSemibold],
        NSForegroundColorAttributeName:UIColor.whiteColor}];
    const CGRect track = CGRectMake(x,27,width,8);
    [[UIColor colorWithWhite:0.16 alpha:1] setFill];
    [[UIBezierPath bezierPathWithRoundedRect:track cornerRadius:3] fill];
    CGRect fill = track;
    fill.size.width *= std::clamp(float(health)/100.0F,0.0F,1.0F);
    [color setFill];
    [[UIBezierPath bezierPathWithRoundedRect:fill cornerRadius:3] fill];
}

- (void)drawRect:(CGRect)rect {
    (void)rect;
    if (!_status || self.bounds.size.width <= 0 || self.bounds.size.height <= 0) return;
    const auto& status = *_status;
    const CGFloat width = (self.bounds.size.width-28)/2;
    [self drawCombatant:_leftName health:status.display_health[0] x:4 width:width
        color:[UIColor colorWithRed:0.18 green:0.83 blue:0.75 alpha:1]];
    [self drawCombatant:_rightName health:status.display_health[1] x:width+24 width:width
        color:[UIColor colorWithRed:0.91 green:0.42 blue:0.39 alpha:1]];
    if (status.damage_text) {
        NSString* damage = [NSString stringWithFormat:@"%d",int(*status.damage_text)];
        [damage drawInRect:CGRectMake(status.damage_on_left ? 4 : width+24,41,width,21) withAttributes:@{
            NSFontAttributeName:[UIFont monospacedDigitSystemFontOfSize:16 weight:UIFontWeightBold],
            NSForegroundColorAttributeName:[UIColor colorWithRed:1 green:0.72 blue:0.35 alpha:1]}];
    }
    _drawnToken = status.token; _drawnRevision = status.revision;
    self.accessibilityLabel = [NSString stringWithFormat:@"%@ HP %d. %@ HP %d.",
        _leftName,int(status.display_health[0]),_rightName,int(status.display_health[1])];
}
@end
