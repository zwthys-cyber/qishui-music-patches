#import "ProbeCore.h"
#import <UIKit/UIKit.h>
#import <objc/runtime.h>
#import <mach-o/dyld.h>

static char QSSeenViewKey;
static BOOL QSInteresting(NSString *name) {
    NSString *lower = name.lowercaseString;
    for (NSString *token in @[@"splash", @"incentive", @"reward", @"lynx", @"advert", @"adview", @"mannor"])
        if ([lower containsString:token]) return YES;
    return NO;
}
static void QSDescribeViews(UIView *view, NSUInteger depth) {
    if (!view || depth > 14) return;
    NSString *name = NSStringFromClass(view.class);
    if (QSInteresting(name) && !objc_getAssociatedObject(view, &QSSeenViewKey)) {
        objc_setAssociatedObject(view, &QSSeenViewKey, @YES, OBJC_ASSOCIATION_RETAIN_NONATOMIC);
        QSLog([NSString stringWithFormat:@"VIEW %@", name]);
    }
    for (UIView *child in view.subviews) QSDescribeViews(child, depth + 1);
}

@interface QSProbe : NSObject
@property (nonatomic, strong) UIButton *button;
@property (nonatomic, weak) UIWindow *hostWindow;
@property (nonatomic, strong) NSTimer *timer;
+ (instancetype)shared;
- (void)attach;
- (void)exportLog;
@end
@implementation QSProbe
+ (instancetype)shared {
    static QSProbe *probe;
    static dispatch_once_t once;
    dispatch_once(&once, ^{ probe = [QSProbe new]; });
    return probe;
}
- (void)attach {
    if (self.button) return;
    UIWindowScene *scene = nil;
    for (UIScene *candidate in UIApplication.sharedApplication.connectedScenes)
        if ([candidate isKindOfClass:UIWindowScene.class] && candidate.activationState == UISceneActivationStateForegroundActive) {
            scene = (UIWindowScene *)candidate; break;
        }
    if (!scene) return;
    UIButton *button = [UIButton buttonWithType:UIButtonTypeSystem];
    button.backgroundColor = [UIColor colorWithRed:0.1 green:0.35 blue:0.8 alpha:0.9];
    button.layer.cornerRadius = 8;
    [button setTitle:@"诊断 D1" forState:UIControlStateNormal];
    [button setTitleColor:UIColor.whiteColor forState:UIControlStateNormal];
    [button addTarget:self action:@selector(exportLog) forControlEvents:UIControlEventTouchUpInside];
    self.button = button;
    QSLog(@"PROBE_D1_UI_ATTACHED");
    __weak QSProbe *weakSelf = self;
    void (^refresh)(void) = ^{
        QSProbe *probe = weakSelf;
        UIWindow *host = nil;
        for (UIWindow *window in scene.windows) {
            if (window.hidden || !window.rootViewController) continue;
            QSDescribeViews(window, 0);
            if (window.isKeyWindow || (!host && window.windowLevel == UIWindowLevelNormal)) host = window;
        }
        if (host) {
            probe.hostWindow = host;
            if (probe.button.superview != host) [host addSubview:probe.button];
            CGFloat top = MAX(host.safeAreaInsets.top, 54);
            probe.button.frame = CGRectMake(12, top + 8, 76, 36);
            [host bringSubviewToFront:probe.button];
        }
    };
    refresh();
    self.timer = [NSTimer scheduledTimerWithTimeInterval:2 repeats:YES block:^(__unused NSTimer *timer) { refresh(); }];
}
- (void)exportLog {
    UIWindowScene *scene = self.hostWindow.windowScene;
    UIViewController *top = nil;
    for (UIWindow *window in scene.windows) {
        if (window.hidden || !window.rootViewController) continue;
        if (window.isKeyWindow || !top) top = window.rootViewController;
    }
    while (top.presentedViewController) top = top.presentedViewController;
    if (!top || [top isKindOfClass:UIActivityViewController.class]) return;
    QSLog(@"USER_EXPORT_LOG");
    NSString *path = [NSTemporaryDirectory() stringByAppendingPathComponent:@"Qishui-Probe-D1.txt"];
    [QSLogSnapshot() writeToFile:path atomically:YES encoding:NSUTF8StringEncoding error:NULL];
    UIActivityViewController *share = [[UIActivityViewController alloc] initWithActivityItems:@[[NSURL fileURLWithPath:path]] applicationActivities:nil];
    share.popoverPresentationController.sourceView = top.view;
    share.popoverPresentationController.sourceRect = CGRectMake(20, 80, 76, 36);
    [top presentViewController:share animated:YES completion:nil];
}
@end

@interface QSProbeInstaller : NSObject
@end
@implementation QSProbeInstaller
+ (void)load {
    @autoreleasepool {
        QSLog([NSString stringWithFormat:@"PROBE_D1_LOADED main_slide=0x%llx", (unsigned long long)_dyld_get_image_vmaddr_slide(0)]);
        Method appeared = class_getInstanceMethod(UIViewController.class, @selector(viewDidAppear:));
        IMP original = method_getImplementation(appeared);
        IMP replacement = imp_implementationWithBlock(^(UIViewController *receiver, BOOL animated) {
            ((void (*)(id, SEL, BOOL))original)(receiver, @selector(viewDidAppear:), animated);
            NSString *name = NSStringFromClass(receiver.class);
            if (![name hasPrefix:@"QSProbe"]) {
                QSLog([NSString stringWithFormat:@"CONTROLLER %@ stack=%@", name, NSThread.callStackReturnAddresses]);
                QSDescribeViews(receiver.view, 0);
            }
        });
        method_setImplementation(appeared, replacement);
        QSTraceObjectMethod(@"BDMannorRewardVideoManager", @"createRewardedVideoWithSourceModel:delegate:completion:");
        QSTraceObjectMethod(@"BDMannorRewardVideoManager", @"loadRewardVideoWithSourceModel:delegate:completion:");
        QSTraceObjectMethod(@"BDMannorRewardVideoManager", @"openRewardVideoWithInfo:viewController:completion:");
        QSTraceObjectMethod(@"BDARewardedVideoAdBaseController", @"openRewardVideoWithInfo:viewController:completion:");
        [NSNotificationCenter.defaultCenter addObserverForName:UIApplicationDidBecomeActiveNotification object:nil queue:NSOperationQueue.mainQueue usingBlock:^(__unused NSNotification *notification) {
            [[QSProbe shared] attach];
        }];
    }
}
@end
