#import "../src/ProbeCore.h"
#include <stdio.h>
@interface QSFixture : NSObject
@property (nonatomic) NSUInteger calls;
@property (nonatomic, strong) NSArray *arguments;
- (void)invoke:(id)a second:(id)b third:(id)c;
- (BOOL)wrong:(id)a second:(id)b third:(id)c;
@end
@implementation QSFixture
- (void)invoke:(id)a second:(id)b third:(id)c {
    self.calls++;
    self.arguments = @[a, b, c];
}
- (BOOL)wrong:(__unused id)a second:(__unused id)b third:(__unused id)c { return YES; }
@end
int main(void) {
    @autoreleasepool {
        if (!QSTraceObjectMethod(@"QSFixture", @"invoke:second:third:")) return 1;
        if (QSTraceObjectMethod(@"QSFixture", @"wrong:second:third:")) return 2;
        if (QSTraceObjectMethod(@"NotPresent", @"invoke:second:third:")) return 3;
        QSFixture *fixture = [QSFixture new];
        NSObject *a = [NSObject new], *b = [NSObject new], *c = [NSObject new];
        [fixture invoke:a second:b third:c];
        if (fixture.calls != 1 || fixture.arguments[0] != a || fixture.arguments[1] != b || fixture.arguments[2] != c) return 4;
        if (![QSLogSnapshot() containsString:@"CALL QSFixture invoke:second:third:"]) return 5;
        puts("Probe forwarding, ABI rejection and missing-class checks passed");
    }
    return 0;
}
