import Foundation

// Samsung exercise_type -> labels / sport hints. Ports the LABEL / RUNNING /
// BIKING tables from samsung_to_tcx.py and samsung_to_gpx.py.

public enum Labels {
    static let running: Set<Int> = [1002, 9001]
    static let biking: Set<Int> = [11007, 15003, 15004, 15005, 15006]

    static let names: [Int: String] = [
        1001: "Walk", 1002: "Run", 9001: "Run", 11007: "Ride",
        13001: "Hike", 15003: "Ride", 15004: "Ride", 14001: "Swim", 0: "Workout",
    ]

    // (label, GPX <type>) for GPX output.
    static let gpx: [Int: (String, String)] = [
        1001: ("Walk", "walking"), 1002: ("Run", "running"), 9001: ("Run", "running"),
        11007: ("Ride", "cycling"), 13001: ("Hike", "hiking"), 14001: ("Swim", "swimming"),
        15003: ("Ride", "cycling"), 15004: ("Ride", "cycling"), 0: ("Workout", "other"),
    ]

    public static func label(for code: Int) -> String { names[code] ?? "Workout" }

    /// TCX Sport attribute (Running / Biking / Other).
    public static func sport(for code: Int) -> String {
        if running.contains(code) { return "Running" }
        if biking.contains(code) { return "Biking" }
        return "Other"
    }

    public static func gpxLabel(for code: Int) -> (String, String) {
        gpx[code] ?? ("Workout", "other")
    }
}
