#import "ProbeCore.h"
#import <objc/runtime.h>
#include <string.h>

static NSMutableArray<NSString *> *QSLines(void) {
    static NSMutableArray<NSString *> *lines;
    static dispatch_once_t once;
    dispatch_once(&once, ^{ lines = [NSMutableArray array]; });
    return lines;
}
void QSLog(NSString *event) {
    NSMutableArray *lines = QSLines();
    @synchronized (lines) {
        [lines addObject:[NSString stringWithFormat:@"%.3f %@", NSDate.timeIntervalSinceReferenceDate, event]];
        if (lines.count > 500) [lines removeObjectsInRange:NSMakeRange(0, lines.count - 500)];
    }
}
NSString *QSLogSnapshot(void) {
    NSMutableArray *lines = QSLines();
    @synchronized (lines) { return [lines componentsJoinedByString:@"\n"]; }
}
BOOL QSTraceObjectMethod(NSString *className, NSString *selectorName) {
    Class cls = NSClassFromString(className);
    SEL sel = NSSelectorFromString(selectorName);
    Method method = cls ? class_getInstanceMethod(cls, sel) : NULL;
    if (!method) { QSLog([NSString stringWithFormat:@"MISSING_%@ %@ %@", cls ? @"METHOD" : @"CLASS", className, selectorName]); return NO; }
    NSMethodSignature *signature = [NSMethodSignature signatureWithObjCTypes:method_getTypeEncoding(method)];
    if (signature.numberOfArguments != 5 || strcmp(signature.methodReturnType, "v") != 0) {
        QSLog([@"SKIP signature " stringByAppendingString:selectorName]); return NO;
    }
    for (NSUInteger i = 2; i < 5; i++) {
        if ([signature getArgumentTypeAtIndex:i][0] != '@') {
            QSLog([@"SKIP non-object " stringByAppendingString:selectorName]); return NO;
        }
    }
    IMP original = method_getImplementation(method);
    IMP replacement = imp_implementationWithBlock(^(id receiver, id a, id b, id c) {
        QSLog([NSString stringWithFormat:@"CALL %@ %@ stack=%@", className, selectorName, NSThread.callStackReturnAddresses]);
        ((void (*)(id, SEL, id, id, id))original)(receiver, sel, a, b, c);
    });
    if (!class_addMethod(cls, sel, replacement, method_getTypeEncoding(method))) {
        method_setImplementation(class_getInstanceMethod(cls, sel), replacement);
    }
    QSLog([NSString stringWithFormat:@"HOOK %@ %@", className, selectorName]);
    return YES;
}
