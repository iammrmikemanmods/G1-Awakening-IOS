#!/usr/bin/env python3
"""Repair v0.3.0 notifyd diagnostics without expanding compatibility bypass."""
import pathlib, sys, subprocess
r=pathlib.Path(sys.argv[1]).resolve()
def edit(file,old,new):
    p=r/file;s=p.read_text()
    if s.count(old)!=1: raise RuntimeError(f'source drift {file}: {s.count(old)}')
    p.write_text(s.replace(old,new,1))

p=r/'Tweak.xm'; s=p.read_text()
a=s.index('static void FIRecordEvent('); b=s.index('static void FIReloadPreferences(',a)
s=s[:a]+'''// Retain each event token for the process lifetime. notifyd deletes a name
// and its recorded state when the last subscriber unregisters.
static NSMutableDictionary<NSString *, NSNumber *> *gFIEventTokens;
static void FIRecordEvent(const char *event) {
    char name[160];
    if (!event || snprintf(name, sizeof(name),
        "com.iammrmikeman.futureinstall.diag.%s", event) >= (int)sizeof(name)) return;
    NSString *key = [NSString stringWithUTF8String:name];
    if (!key) return;
    @synchronized ([NSProcessInfo class]) {
        if (!gFIEventTokens) gFIEventTokens = [NSMutableDictionary dictionary];
        NSNumber *cached = gFIEventTokens[key];
        int token;
        if (cached) token = [cached intValue];
        else {
            uint32_t status = notify_register_check(name, &token);
            if (status != NOTIFY_STATUS_OK) {
                NSLog(@"[FutureInstall] diagnostic register error %u", status);
                return;
            }
            gFIEventTokens[key] = @(token);
        }
        uint64_t stamp = (uint64_t)[[NSDate date] timeIntervalSince1970];
        uint32_t status = notify_set_state(token, stamp);
        if (status == NOTIFY_STATUS_OK) notify_post(name);
        else NSLog(@"[FutureInstall] diagnostic state error %u", status);
    }
}

'''+s[b:];p.write_text(s)

ui='FutureInstallPrefs/FIRootListController.m'
selftest='''// Settings-only transport proof. PASS does not prove daemon injection.
static NSString *FINotifySelfTest(void) {
    const char *name = "com.iammrmikeman.futureinstall.diag.settings.roundtrip";
    int writer=-1, reader=-1;
    uint32_t status = notify_register_check(name, &writer);
    if (status != NOTIFY_STATUS_OK)
        return [NSString stringWithFormat:@"FAIL register %u", status];
    uint64_t stamp = ((uint64_t)[[NSDate date] timeIntervalSince1970] << 1) | 1;
    status = notify_set_state(writer, stamp);
    if (status == NOTIFY_STATUS_OK) status = notify_register_check(name, &reader);
    uint64_t received = 0;
    if (status == NOTIFY_STATUS_OK) status = notify_get_state(reader, &received);
    if (reader >= 0) notify_cancel(reader);
    notify_cancel(writer);
    if (status == NOTIFY_STATUS_OK && received == stamp) return @"PASS";
    return [NSString stringWithFormat:@"FAIL status=%u match=%d",status,received==stamp];
}

'''
edit(ui,'@interface FIRootListController : PSListController',selftest+'@interface FIRootListController : PSListController')
edit(ui,'    [lines addObject:@"\\nInjection / request events (best effort):"];',
     '    [lines addObject:[NSString stringWithFormat:@"Settings notify test: %@", FINotifySelfTest()]];\n'
     '    [lines addObject:@"Injection / request events (while processes are alive):"];')
edit(ui,'active ? @"ACTIVE" : @"OFF/EXPIRED"','active ? @"CONFIG ACTIVE" : @"OFF/EXPIRED"')
edit(ui,'    [self FIShowAlert:@"FutureInstall diagnostics"',
     '    [lines addObject:@"CONFIG ACTIVE means prefs enabled, not an injected hook. Events disappear when their emitting process exits."];\n'
     '    [self FIShowAlert:@"FutureInstall diagnostics"')
edit('control','Version: 0.3.0','Version: 0.3.1')
edit('FutureInstallPrefs/Resources/Info.plist','<string>0.3.0</string>','<string>0.3.1</string>')
edit('tests/validate_deb.py',"fields['Version'] != '0.3.0'","fields['Version'] != '0.3.1'")
edit('tests/validate_source.py','    def test_source_manifest_integrity(self):',
'''    def test_diagnostics_token_lifetime(self):
        tweak = (ROOT / 'Tweak.xm').read_text()
        body = tweak.split('static void FIRecordEvent(',1)[1].split('static void FIReloadPreferences(',1)[0]
        self.assertIn('gFIEventTokens[key] = @(token)',body)
        self.assertNotIn('notify_cancel(',body)
        ui = (ROOT / 'FutureInstallPrefs/FIRootListController.m').read_text()
        self.assertIn('FINotifySelfTest()',ui)
        self.assertIn('received == stamp',ui)

    def test_source_manifest_integrity(self):''')
for rel in ('README.md','docs/VERIFICATION_REPORT.md'):
    with (r/rel).open('a') as f:
        f.write('\n## v0.3.1 notifyd diagnostic repair\n')
        f.write('The iOS 17.5.1 device showed App Store iOS 26 rejection and all-zero telemetry. '
                'v0.3.0 cancelled the only Darwin notify registration immediately after setting state; '
                'notifyd may release the name and lose the state. v0.3.1 keeps event registrations '
                'alive until process exit and adds an independent Settings notify round-trip test. '
                'This does not alter version-spoofing hooks or prove App Store download support.\n')
edit('README.md','**Version:** 0.3.0','**Version:** 0.3.1')
subprocess.run([sys.executable,str(r/'scripts/update_manifest.py')],check=True)
print('Applied v0.3.1 diagnostic patch')
