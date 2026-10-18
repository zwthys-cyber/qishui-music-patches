#import <UIKit/UIKit.h>
#import <objc/runtime.h>
#import <mach-o/dyld.h>
#import "AdFlow.h"
#import "ProbeCore.h"
#include <string.h>

static char QSAttemptKey, QSFirstFrameSeenKey;
static IMP QSOriginalFirstFrame, QSOriginalFirstFrameSDK, QSOriginalAppeared, QSOriginalReuse;
static BOOL QSMethodMatches(Class cls, SEL selector, NSUInteger count, const char *returnType) {
    Method method = class_getInstanceMethod(cls, selector);
    if (!method) return NO;
    NSMethodSignature *signature = [NSMethodSignature signatureWithObjCTypes:method_getTypeEncoding(method)];
    return signature.numberOfArguments == count && strcmp(signature.methodReturnType, returnType) == 0;
}
static void QSPollEffective(UIViewController *controller, QSAdAttempt *attempt, NSUInteger remaining) {
    // newLoadState bit 0x40 is set by the SDK's own videoBecomeInspired method.
    SEL stateSelector = NSSelectorFromString(@"newLoadState");
    NSUInteger state = ((NSUInteger (*)(id, SEL))[controller methodForSelector:stateSelector])(controller, stateSelector);
    if (state & 0x40) {
        if ([attempt closeIfEffective:YES]) {
            QSLog(@"R3_EFFECTIVE_SDK_FLAG close_scheduled");
            dispatch_after(dispatch_time(DISPATCH_TIME_NOW, 800 * NSEC_PER_MSEC), dispatch_get_main_queue(), ^{
                if (!controller.viewIfLoaded.window) { QSLog(@"R3_ALREADY_DISMISSED"); return; }
                SEL closeSelector = NSSelectorFromString(@"close");
                QSLog(@"R3_CLOSE_EXISTING_SDK_FLOW");
                ((void (*)(id, SEL))[controller methodForSelector:closeSelector])(controller, closeSelector);
            });
        }
    } else if (remaining) {
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, 250 * NSEC_PER_MSEC), dispatch_get_main_queue(), ^{
            if (controller.viewIfLoaded.window) QSPollEffective(controller, attempt, remaining - 1);
        });
    } else {
        QSLog(@"R3_NO_EFFECTIVE_FLAG leaving_original_flow_running");
    }
}
static void QSScheduleIfReady(UIViewController *controller) {
    if (!objc_getAssociatedObject(controller, &QSFirstFrameSeenKey)) return;
    if (!controller.viewIfLoaded.window || UIApplication.sharedApplication.applicationState != UIApplicationStateActive) { QSLog(@"R3_FIRST_FRAME_DEFERRED_UNTIL_VISIBLE"); return; }
    QSAdAttempt *attempt = objc_getAssociatedObject(controller, &QSAttemptKey);
    if (!attempt) {
        attempt = [QSAdAttempt new];
        objc_setAssociatedObject(controller, &QSAttemptKey, attempt, OBJC_ASSOCIATION_RETAIN_NONATOMIC);
    }
    if (![attempt schedule]) return;
    QSLog(@"R3_VISIBLE_FIRST_FRAME schedule_existing_reward_callback");
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, 150 * NSEC_PER_MSEC), dispatch_get_main_queue(), ^{
        if (![attempt invokeIfVisible:(controller.viewIfLoaded.window != nil && UIApplication.sharedApplication.applicationState == UIApplicationStateActive)]) {
            QSLog(@"R3_NOT_VISIBLE callback_not_invoked");
            objc_setAssociatedObject(controller, &QSAttemptKey, nil, OBJC_ASSOCIATION_RETAIN_NONATOMIC);
            return;
        }
        SEL inspired = NSSelectorFromString(@"videoBecomeInspired");
        QSLog(@"R3_INVOKE_EXISTING_videoBecomeInspired");
        ((void (*)(id, SEL))[controller methodForSelector:inspired])(controller, inspired);
        QSPollEffective(controller, attempt, 12);
    });
}
static void QSFirstFrame(id receiver, SEL selector) {
    ((void (*)(id, SEL))QSOriginalFirstFrame)(receiver, selector);
    QSLog(@"R3_FIRST_FRAME_JS");
    dispatch_async(dispatch_get_main_queue(), ^{
        objc_setAssociatedObject(receiver, &QSFirstFrameSeenKey, @YES, OBJC_ASSOCIATION_RETAIN_NONATOMIC);
        QSScheduleIfReady(receiver);
    });
}
static void QSFirstFrameSDK(id receiver, SEL selector) {
    ((void (*)(id, SEL))QSOriginalFirstFrameSDK)(receiver, selector);
    QSLog(@"R3_FIRST_FRAME_SDK");
    dispatch_async(dispatch_get_main_queue(), ^{
        objc_setAssociatedObject(receiver, &QSFirstFrameSeenKey, @YES, OBJC_ASSOCIATION_RETAIN_NONATOMIC);
        QSScheduleIfReady(receiver);
    });
}
static void QSAppeared(id receiver, SEL selector, BOOL animated) {
    ((void (*)(id, SEL, BOOL))QSOriginalAppeared)(receiver, selector, animated);
    QSLog(@"R3_TARGET_CONTROLLER_APPEARED");
    QSScheduleIfReady(receiver);
}
static void QSReuse(id receiver, SEL selector) {
    ((void (*)(id, SEL))QSOriginalReuse)(receiver, selector);
    objc_setAssociatedObject(receiver, &QSAttemptKey, nil, OBJC_ASSOCIATION_RETAIN_NONATOMIC);
    objc_setAssociatedObject(receiver, &QSFirstFrameSeenKey, nil, OBJC_ASSOCIATION_RETAIN_NONATOMIC);
    QSLog(@"R3_CONTROLLER_REUSE_RESET");
}
static IMP QSInstall(Class cls, SEL selector, IMP replacement) {
    Method method = class_getInstanceMethod(cls, selector);
    IMP original = method_getImplementation(method);
    if (!class_addMethod(cls, selector, replacement, method_getTypeEncoding(method)))
        method_setImplementation(class_getInstanceMethod(cls, selector), replacement);
    return original;
}
@interface QSNoAdsInstaller : NSObject
@end
@implementation QSNoAdsInstaller
+ (void)load {
    @autoreleasepool {
        QSLog(@"R3_1_RUNTIME_LOADED");
        NSBundle *bundle = NSBundle.mainBundle;
        QSLog([NSString stringWithFormat:@"R3_1_BUNDLE build=%@ marker=%@", [bundle objectForInfoDictionaryKey:@"CFBundleVersion"], [bundle objectForInfoDictionaryKey:@"QSProbeBuild"]]);
        BOOL oldModifierPresent = NO;
        for (uint32_t i = 0; i < _dyld_image_count(); i++) {
            const char *raw = _dyld_get_image_name(i);
            if (!raw) continue;
            NSString *name = [NSString stringWithUTF8String:raw].lastPathComponent;
            if ([name isEqualToString:@"QishuiR3.dylib"]) oldModifierPresent = YES;
            if ([name containsString:@"Qishui"] || [name containsString:@"Probe"])
                QSLog([NSString stringWithFormat:@"R3_1_LIBRARY %@ header=%p", name, (const void *)_dyld_get_image_header(i)]);
        }
        if (oldModifierPresent) {
            QSLog(@"R3_1_OLD_MODIFIER_PRESENT avoiding_duplicate_reward_hooks");
            return;
        }
        Class cls = NSClassFromString(@"BDARVLynxViewController");
        SEL firstFrame = NSSelectorFromString(@"videoFirstFrame");
        SEL sdkFrame = NSSelectorFromString(@"videoFirstFrameSDK");
        SEL inspired = NSSelectorFromString(@"videoBecomeInspired");
        SEL closeSelector = NSSelectorFromString(@"close");
        SEL stateSelector = NSSelectorFromString(@"newLoadState");
        SEL appeared = @selector(viewDidAppear:);
        SEL reuse = NSSelectorFromString(@"prepareForReuse");
        if (!cls || !QSMethodMatches(cls, firstFrame, 2, "v") || !QSMethodMatches(cls, sdkFrame, 2, "v") ||
            !QSMethodMatches(cls, inspired, 2, "v") || !QSMethodMatches(cls, closeSelector, 2, "v") ||
            !QSMethodMatches(cls, stateSelector, 2, @encode(NSUInteger)) || !QSMethodMatches(cls, appeared, 3, "v") ||
            !QSMethodMatches(cls, reuse, 2, "v")) {
            QSLog(@"R3_ABI_MISMATCH no_reward_hook_installed");
            return;
        }
        QSOriginalFirstFrame = QSInstall(cls, firstFrame, (IMP)QSFirstFrame);
        QSOriginalFirstFrameSDK = QSInstall(cls, sdkFrame, (IMP)QSFirstFrameSDK);
        QSOriginalAppeared = QSInstall(cls, appeared, (IMP)QSAppeared);
        QSOriginalReuse = QSInstall(cls, reuse, (IMP)QSReuse);
        QSLog(@"R3_HOOK_INSTALLED BDARVLynxViewController first_frame_and_visibility");
    }
}
@end
