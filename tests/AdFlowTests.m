#import "../src/AdFlow.h"
#include <stdio.h>
int main(void) {
    @autoreleasepool {
        QSAdAttempt *attempt = [QSAdAttempt new];
        if ([attempt invokeIfVisible:YES] || [attempt closeIfEffective:YES]) return 1;
        if (![attempt schedule] || [attempt schedule]) return 2;
        if ([attempt invokeIfVisible:NO] || attempt.invoked) return 3;
        if (![attempt invokeIfVisible:YES] || [attempt invokeIfVisible:YES]) return 4;
        if ([attempt closeIfEffective:NO] || attempt.closed) return 5;
        if (![attempt closeIfEffective:YES] || [attempt closeIfEffective:YES]) return 6;
        puts("Per-controller once-only reward attempt, visibility guard and effective-state close guard passed");
    }
    return 0;
}
