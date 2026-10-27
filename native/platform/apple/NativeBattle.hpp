#pragma once

#import <UIKit/UIKit.h>
#include "NativeBitmapFont.hpp"
#include "NativeSourceArt.hpp"
#include "g1/M3GBattlePresentation.hpp"
#include <algorithm>

// Native point-based HUD over the original animated M3G presentation. Every
// health/damage value comes from the recovered controller; this view has no
// private animation clock, invented HP tween or gameplay acknowledgement.
@interface G1BattleCanvas : UIView
- (void)resetPresentation;
- (void)loadOriginalFonts:(const g1::Archive&)archive;
- (void)showStatus:(const g1::M3GBattleStatus&)status left:(NSString*)left right:(NSString*)right
        leftFaction:(std::uint8_t)leftFaction rightFaction:(std::uint8_t)rightFaction;
- (BOOL)hasDrawnToken:(std::uint64_t)token revision:(std::uint64_t)revision;
@end

@implementation G1BattleCanvas {
    std::optional<g1::M3GBattleStatus> _status;
    NSString* _leftName;
    NSString* _rightName;
    std::uint64_t _drawnToken, _drawnRevision;
    G1BitmapFontFace* _originalNameFont;
    UIImage* _sourceFrame;
    UIImage* _redGrid;
    UIImage* _purpleGrid;
    std::uint8_t _leftFaction,_rightFaction;
}

- (instancetype)initWithFrame:(CGRect)frame {
    self = [super initWithFrame:frame];
    if (self) { self.opaque = NO; self.clipsToBounds = YES; self.isAccessibilityElement = YES; }
    return self;
}

- (void)loadOriginalFonts:(const g1::Archive&)archive {
    _originalNameFont=[[G1BitmapFontFace alloc] initWithArchive:archive slot:2];
    _sourceFrame=g1::source_art::png(archive,1038,156,58);
    _redGrid=g1::source_art::png(archive,874,128,63);
    _purpleGrid=g1::source_art::png(archive,799,128,63);
    _drawnToken=0; _drawnRevision=0;
    [self setNeedsDisplay];
}

- (void)showStatus:(const g1::M3GBattleStatus&)status left:(NSString*)left right:(NSString*)right
        leftFaction:(std::uint8_t)leftFaction rightFaction:(std::uint8_t)rightFaction {
    if (_status && _status->token == status.token && _status->revision == status.revision &&
        _leftFaction==leftFaction && _rightFaction==rightFaction) return;
    _leftFaction=leftFaction;_rightFaction=rightFaction;
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

- (void)drawCombatant:(NSString*)name health:(std::int32_t)health
                    x:(CGFloat)x faction:(std::uint8_t)faction {
    // 1038 is the original 156x58 mechanical plate with alpha windows;
    // 874/799 are the genuine red/purple animated-style grid textures.
    UIImage* grid=faction==0?_redGrid:_purpleGrid;
    if(grid)[grid drawInRect:CGRectMake(x+6,7,144,50)];
    if(_sourceFrame)[_sourceFrame drawInRect:CGRectMake(x,0,156,58)];
    UIColor* color=faction==0 ?
        [UIColor colorWithRed:1 green:0.32 blue:0.33 alpha:1] :
        [UIColor colorWithRed:0.8 green:0.36 blue:1 alpha:1];
    NSString* hp=[NSString stringWithFormat:@"%d",int(health)];
    const CGRect hpRect=CGRectMake(x+61,16,79,17);
    if([_originalNameFont supportsText:hp] &&
       [_originalNameFont sizeForText:hp height:16].width<hpRect.size.width)
        [_originalNameFont drawText:hp rect:hpRect height:16 alignment:NSTextAlignmentCenter];
    else [hp drawInRect:hpRect withAttributes:@{NSFontAttributeName:
         [UIFont fontWithName:@"Menlo-Bold" size:16] ?: [UIFont boldSystemFontOfSize:16],
         NSForegroundColorAttributeName:color}];
    const CGRect nameRect=CGRectMake(x+25,36,113,18);
    if([_originalNameFont supportsText:name] &&
       [_originalNameFont sizeForText:name height:12].width<=nameRect.size.width)
        [_originalNameFont drawText:name rect:nameRect height:12 alignment:NSTextAlignmentCenter];
    else [name drawInRect:nameRect withAttributes:@{NSFontAttributeName:
         [UIFont fontWithName:@"Menlo-Bold" size:12] ?: [UIFont boldSystemFontOfSize:12],
         NSForegroundColorAttributeName:color}];
}

- (void)drawRect:(CGRect)rect {
    (void)rect;
    if (!_status || self.bounds.size.width <= 0 || self.bounds.size.height <= 0) return;
    CGContextRef ctx=UIGraphicsGetCurrentContext();if(!ctx)return;
    CGContextSaveGState(ctx);
    CGContextScaleCTM(ctx,self.bounds.size.width/480.0,self.bounds.size.height/64.0);
    CGContextSetInterpolationQuality(ctx,kCGInterpolationNone);
    CGContextSetShouldAntialias(ctx,false);
    const auto& status=*_status;
    [self drawCombatant:_leftName health:status.display_health[0] x:0 faction:_leftFaction];
    [self drawCombatant:_rightName health:status.display_health[1] x:324 faction:_rightFaction];
    // Only display actual native battle damage returned by the presentation
    // clock. Never invent or tween a number to manufacture combat progress.
    if(status.damage_text) {
        NSString* amount=[NSString stringWithFormat:@"%d",int(*status.damage_text)];
        CGRect place=status.damage_on_left ? CGRectMake(4,1,144,23):CGRectMake(326,1,144,23);
        [amount drawInRect:place withAttributes:@{
            NSFontAttributeName:[UIFont fontWithName:@"Menlo-Bold" size:21] ?: [UIFont boldSystemFontOfSize:21],
            NSForegroundColorAttributeName:[UIColor colorWithRed:1 green:0.77 blue:0.28 alpha:1]}];
    }
    CGContextRestoreGState(ctx);
    _drawnToken=status.token;_drawnRevision=status.revision;
    self.accessibilityLabel=[NSString stringWithFormat:@"%@ HP %d. %@ HP %d.",
        _leftName,int(status.display_health[0]),_rightName,int(status.display_health[1])];
}
@end
