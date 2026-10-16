"""Writes STAWNQCMS.xcodeproj/project.pbxproj for every Swift file in STAWNQCMS/ (no XcodeGen needed)."""
import hashlib, os, sys
ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "STAWNQCMS")
VERSION = sys.argv[1] if len(sys.argv) > 1 else "1.0.0"
BUILD = sys.argv[2] if len(sys.argv) > 2 else "1"
BUNDLE = "com.stawnprecision.qcms"

def uid(name):
    return hashlib.md5(name.encode()).hexdigest()[:24].upper()

swift = sorted(f for f in os.listdir(SRC) if f.endswith(".swift"))
resources = ["Assets.xcassets", "Resources/catalog.json"]
objs = []
P = lambda k, v: objs.append(f"\t\t{k} = {v};")
files = []
for f in swift:
    ref, bf = uid("ref" + f), uid("bf" + f)
    P(ref, f'{{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = "{f}"; sourceTree = "<group>"; }}')
    P(bf, f'{{isa = PBXBuildFile; fileRef = {ref}; }}')
    files.append((ref, bf))
res = []
for r in resources:
    ref, bf = uid("ref" + r), uid("bf" + r)
    kind = "folder.assetcatalog" if r.endswith("xcassets") else "text.json"
    P(ref, f'{{isa = PBXFileReference; lastKnownFileType = {kind}; path = "{r}"; sourceTree = "<group>"; }}')
    P(bf, f'{{isa = PBXBuildFile; fileRef = {ref}; }}')
    res.append((ref, bf))
plist = uid("refInfo.plist")
P(plist, '{isa = PBXFileReference; lastKnownFileType = text.plist.xml; path = Info.plist; sourceTree = "<group>"; }')
app = uid("product")
P(app, '{isa = PBXFileReference; explicitFileType = wrapper.application; includeInIndex = 0; path = "STAWN QCMS.app"; sourceTree = BUILT_PRODUCTS_DIR; }')
main, grp, prods = uid("maingroup"), uid("srcgroup"), uid("products")
P(grp, "{isa = PBXGroup; children = (" + ", ".join([r for r, _ in files] + [r for r, _ in res] + [plist]) + '); path = STAWNQCMS; sourceTree = "<group>"; }')
P(prods, "{isa = PBXGroup; children = (" + app + '); name = Products; sourceTree = "<group>"; }')
P(main, "{isa = PBXGroup; children = (" + grp + ", " + prods + '); sourceTree = "<group>"; }')
srcp, frp, resp = uid("sources"), uid("frameworks"), uid("resources")
P(srcp, "{isa = PBXSourcesBuildPhase; buildActionMask = 2147483647; files = (" + ", ".join(b for _, b in files) + "); runOnlyForDeploymentPostprocessing = 0; }")
P(frp, "{isa = PBXFrameworksBuildPhase; buildActionMask = 2147483647; files = (); runOnlyForDeploymentPostprocessing = 0; }")
P(resp, "{isa = PBXResourcesBuildPhase; buildActionMask = 2147483647; files = (" + ", ".join(b for _, b in res) + "); runOnlyForDeploymentPostprocessing = 0; }")

common = {
    "ALWAYS_SEARCH_USER_PATHS": "NO", "CLANG_ENABLE_MODULES": "YES", "CLANG_ENABLE_OBJC_ARC": "YES", "ENABLE_STRICT_OBJC_MSGSEND": "YES",
    "GCC_C_LANGUAGE_STANDARD": "gnu11", "IPHONEOS_DEPLOYMENT_TARGET": "16.0", "SDKROOT": "iphoneos", "SWIFT_VERSION": "5.0",
    "SWIFT_STRICT_CONCURRENCY": "minimal",
}
def settings(d):
    return "{" + " ".join(f'{k} = "{v}";' for k, v in d.items()) + "}"
pd, pr = uid("projdebug"), uid("projrelease")
P(pd, "{isa = XCBuildConfiguration; buildSettings = " + settings({**common, "DEBUG_INFORMATION_FORMAT": "dwarf", "ONLY_ACTIVE_ARCH": "YES", "ENABLE_TESTABILITY": "YES",
   "SWIFT_OPTIMIZATION_LEVEL": "-Onone", "SWIFT_ACTIVE_COMPILATION_CONDITIONS": "DEBUG", "GCC_OPTIMIZATION_LEVEL": "0"}) + "; name = Debug; }")
P(pr, "{isa = XCBuildConfiguration; buildSettings = " + settings({**common, "DEBUG_INFORMATION_FORMAT": "dwarf-with-dsym", "VALIDATE_PRODUCT": "YES",
   "SWIFT_COMPILATION_MODE": "wholemodule", "SWIFT_OPTIMIZATION_LEVEL": "-O"}) + "; name = Release; }")
target_common = {
    "ASSETCATALOG_COMPILER_APPICON_NAME": "AppIcon", "ASSETCATALOG_COMPILER_GLOBAL_ACCENT_COLOR_NAME": "AccentColor", "CODE_SIGN_STYLE": "Automatic",
    "CURRENT_PROJECT_VERSION": BUILD, "MARKETING_VERSION": VERSION, "DEVELOPMENT_TEAM": "", "GENERATE_INFOPLIST_FILE": "NO",
    "INFOPLIST_FILE": "STAWNQCMS/Info.plist", "LD_RUNPATH_SEARCH_PATHS": "$(inherited) @executable_path/Frameworks", "PRODUCT_BUNDLE_IDENTIFIER": BUNDLE,
    "PRODUCT_NAME": "STAWN QCMS", "SUPPORTED_PLATFORMS": "iphoneos iphonesimulator", "SUPPORTS_MACCATALYST": "NO", "TARGETED_DEVICE_FAMILY": "1,2",
    "SWIFT_EMIT_LOC_STRINGS": "NO", "ENABLE_PREVIEWS": "YES",
}
td, tr = uid("targetdebug"), uid("targetrelease")
P(td, "{isa = XCBuildConfiguration; buildSettings = " + settings(target_common) + "; name = Debug; }")
P(tr, "{isa = XCBuildConfiguration; buildSettings = " + settings(target_common) + "; name = Release; }")
pl, tl = uid("projlist"), uid("targetlist")
P(pl, "{isa = XCConfigurationList; buildConfigurations = (" + pd + ", " + pr + "); defaultConfigurationIsVisible = 0; defaultConfigurationName = Release; }")
P(tl, "{isa = XCConfigurationList; buildConfigurations = (" + td + ", " + tr + "); defaultConfigurationIsVisible = 0; defaultConfigurationName = Release; }")
target, proj = uid("target"), uid("project")
P(target, "{isa = PBXNativeTarget; buildConfigurationList = " + tl + "; buildPhases = (" + srcp + ", " + frp + ", " + resp + '); buildRules = (); dependencies = (); name = STAWNQCMS; productName = STAWNQCMS; productReference = ' + app + '; productType = "com.apple.product-type.application"; }')
P(proj, "{isa = PBXProject; attributes = {BuildIndependentTargetsInParallel = 1; LastSwiftUpdateCheck = 1500; LastUpgradeCheck = 1500; TargetAttributes = {" + target + ' = {CreatedOnToolsVersion = 15.0; }; }; }; buildConfigurationList = ' + pl + '; compatibilityVersion = "Xcode 14.0"; developmentRegion = en; hasScannedForEncodings = 0; knownRegions = (en, Base); mainGroup = ' + main + "; productRefGroup = " + prods + '; projectDirPath = ""; projectRoot = ""; targets = (' + target + "); }")
out = "// !$*UTF8*$!\n{\n\tarchiveVersion = 1;\n\tclasses = {\n\t};\n\tobjectVersion = 56;\n\tobjects = {\n" + "\n".join(sorted(objs)) + "\n\t};\n\trootObject = " + proj + ";\n}\n"
os.makedirs(os.path.join(ROOT, "STAWNQCMS.xcodeproj"), exist_ok=True)
open(os.path.join(ROOT, "STAWNQCMS.xcodeproj", "project.pbxproj"), "w").write(out)
# shared scheme so xcodebuild / Xcode Cloud can find it
sd = os.path.join(ROOT, "STAWNQCMS.xcodeproj", "xcshareddata", "xcschemes"); os.makedirs(sd, exist_ok=True)
open(os.path.join(sd, "STAWNQCMS.xcscheme"), "w").write(f'''<?xml version="1.0" encoding="UTF-8"?>
<Scheme LastUpgradeVersion = "1500" version = "1.7">
   <BuildAction parallelizeBuildables = "YES" buildImplicitDependencies = "YES">
      <BuildActionEntries>
         <BuildActionEntry buildForTesting = "YES" buildForRunning = "YES" buildForProfiling = "YES" buildForArchiving = "YES" buildForAnalyzing = "YES">
            <BuildableReference BuildableIdentifier = "primary" BlueprintIdentifier = "{target}" BuildableName = "STAWN QCMS.app" BlueprintName = "STAWNQCMS" ReferencedContainer = "container:STAWNQCMS.xcodeproj"></BuildableReference>
         </BuildActionEntry>
      </BuildActionEntries>
   </BuildAction>
   <LaunchAction buildConfiguration = "Debug" selectedDebuggerIdentifier = "Xcode.DebuggerFoundation.Debugger.LLDB" selectedLauncherIdentifier = "Xcode.DebuggerFoundation.Launcher.LLDB" launchStyle = "0" useCustomWorkingDirectory = "NO" ignoresPersistentStateOnLaunch = "NO" debugDocumentVersioning = "YES" debugServiceExtension = "internal" allowLocationSimulation = "YES">
      <BuildableProductRunnable runnableDebuggingMode = "0">
         <BuildableReference BuildableIdentifier = "primary" BlueprintIdentifier = "{target}" BuildableName = "STAWN QCMS.app" BlueprintName = "STAWNQCMS" ReferencedContainer = "container:STAWNQCMS.xcodeproj"></BuildableReference>
      </BuildableProductRunnable>
   </LaunchAction>
   <ArchiveAction buildConfiguration = "Release" revealArchiveInOrganizer = "YES"></ArchiveAction>
</Scheme>
''')
print("project with", len(swift), "swift files")
