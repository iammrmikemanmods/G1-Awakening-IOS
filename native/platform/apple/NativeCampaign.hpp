#pragma once

#import <UIKit/UIKit.h>
#include <algorithm>
#include <cmath>
#include <cstdint>

@interface G1WorldTitleLabel : UILabel
- (BOOL)currentTextDrawn;
@end
@implementation G1WorldTitleLabel {
    NSUInteger _textRevision,_drawnTextRevision;
}
- (void)setText:(NSString*)text {
    if([self.text isEqualToString:text])return;
    [super setText:text];++_textRevision;[self setNeedsDisplay];
}
- (void)drawTextInRect:(CGRect)rect {
    [super drawTextInRect:rect];_drawnTextRevision=_textRevision;
}
- (BOOL)currentTextDrawn { return _textRevision>0 && _textRevision==_drawnTextRevision; }
@end

// Native campaign/menu/results surface. A token is visible only after its
// current text has actually drawn. This is not an original background or font.
@interface G1CampaignCanvas : UIView
- (void)showTitle:(NSString*)title body:(NSString*)body token:(std::uint64_t)token;
- (void)resetPresentation;
- (std::uint64_t)drawnToken;
- (CGFloat)heightForWidth:(CGFloat)width;
- (void)setBackgroundOffset:(std::int32_t)offset;
@end

@implementation G1CampaignCanvas {
    NSString* _heading;
    NSString* _body;
    std::uint64_t _token, _drawnToken;
    std::int32_t _backgroundOffset;
}
- (instancetype)initWithFrame:(CGRect)frame {
    self=[super initWithFrame:frame];
    if(self) { self.opaque=YES; self.isAccessibilityElement=YES; self.clipsToBounds=YES; }
    return self;
}
- (NSDictionary*)bodyAttributes {
    NSMutableParagraphStyle* paragraph=[NSMutableParagraphStyle new];
    paragraph.lineSpacing=4;
    paragraph.lineBreakMode=NSLineBreakByWordWrapping;
    return @{NSFontAttributeName:[UIFont systemFontOfSize:16 weight:UIFontWeightMedium],
        NSForegroundColorAttributeName:UIColor.whiteColor,NSParagraphStyleAttributeName:paragraph};
}
- (void)showTitle:(NSString*)title body:(NSString*)body token:(std::uint64_t)token {
    if(_token==token && [_heading isEqualToString:title] && [_body isEqualToString:body])return;
    _heading=[title copy];_body=[body copy];_token=token;_drawnToken=0;_backgroundOffset=0;
    self.accessibilityLabel=[NSString stringWithFormat:@"%@. %@",title,body];
    [self setNeedsDisplay];
}
- (void)resetPresentation {
    _heading=nil;_body=nil;_token=0;_drawnToken=0;_backgroundOffset=0;
    self.accessibilityLabel=@"";[self setNeedsDisplay];
}
- (CGFloat)heightForWidth:(CGFloat)width {
    if(width<=32)return 0;
    const CGRect body=[_body ?: @"" boundingRectWithSize:CGSizeMake(width-32,CGFLOAT_MAX)
        options:NSStringDrawingUsesLineFragmentOrigin|NSStringDrawingUsesFontLeading
        attributes:[self bodyAttributes] context:nil];
    return std::max(CGFloat(150),CGFloat(90)+std::ceil(body.size.height));
}
- (std::uint64_t)drawnToken { return _drawnToken; }
- (void)setBackgroundOffset:(std::int32_t)offset {
    if(_backgroundOffset==offset)return;
    _backgroundOffset=offset;[self setNeedsDisplay];
}
- (void)drawRect:(CGRect)rect {
    (void)rect;
    if(self.bounds.size.width<=32 || self.bounds.size.height<=0 || !_heading || !_body)return;
    [[UIColor colorWithRed:0.025 green:0.045 blue:0.075 alpha:1] setFill];
    UIRectFill(self.bounds);
    // The recovered results accumulator drives this native background. Its
    // pattern is a host UI choice, never a claim of original image fidelity.
    [[UIColor colorWithWhite:0.5 alpha:0.06] setFill];
    const CGFloat phase=std::fmod(static_cast<double>(_backgroundOffset)/65536.0,48.0);
    for(CGFloat y=phase-48;y<self.bounds.size.height;y+=48)
        UIRectFill(CGRectMake(0,y,self.bounds.size.width,1));
    [_heading drawInRect:CGRectMake(16,14,self.bounds.size.width-32,34) withAttributes:@{
        NSFontAttributeName:[UIFont systemFontOfSize:22 weight:UIFontWeightBold],
        NSForegroundColorAttributeName:[UIColor colorWithRed:1 green:0.84 blue:0.25 alpha:1]}];
    [_body drawWithRect:CGRectMake(16,62,self.bounds.size.width-32,self.bounds.size.height-74)
        options:NSStringDrawingUsesLineFragmentOrigin|NSStringDrawingUsesFontLeading
        attributes:[self bodyAttributes] context:nil];
    _drawnToken=_token;
}
@end
