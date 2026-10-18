#import <Foundation/Foundation.h>
// Tracks one attempt per controller. No server response or account state is modified.
@interface QSAdAttempt : NSObject
@property (nonatomic, readonly) BOOL scheduled;
@property (nonatomic, readonly) BOOL invoked;
@property (nonatomic, readonly) BOOL closed;
- (BOOL)schedule;
- (BOOL)invokeIfVisible:(BOOL)visible;
- (BOOL)closeIfEffective:(BOOL)effective;
@end
