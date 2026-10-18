#import "AdFlow.h"
@implementation QSAdAttempt
- (BOOL)schedule {
    if (_scheduled) return NO;
    _scheduled = YES;
    return YES;
}
- (BOOL)invokeIfVisible:(BOOL)visible {
    if (!_scheduled || _invoked || !visible) return NO;
    _invoked = YES;
    return YES;
}
- (BOOL)closeIfEffective:(BOOL)effective {
    if (!_invoked || _closed || !effective) return NO;
    _closed = YES;
    return YES;
}
@end
