// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "StravaToolkitKit",
    platforms: [.macOS(.v13), .iOS(.v16)],
    products: [
        .library(name: "StravaToolkitKit", targets: ["StravaToolkitKit"]),
        .executable(name: "stkcheck", targets: ["stkcheck"]),
    ],
    targets: [
        .target(name: "StravaToolkitKit"),
        // Headless verification harness — runnable without Xcode/XCTest:
        //   swift run stkcheck <path-to-Fixtures>
        .executableTarget(name: "stkcheck", dependencies: ["StravaToolkitKit"]),
        // Full test suite for use in Xcode (uses swift-testing):
        .testTarget(
            name: "StravaToolkitKitTests",
            dependencies: ["StravaToolkitKit"],
            resources: [.copy("Fixtures")]
        ),
    ]
)
