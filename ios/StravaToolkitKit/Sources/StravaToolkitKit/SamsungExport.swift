import Foundation

/// Locates and reads a Samsung Health export directory tree.
public enum SamsungExport {

    public struct Root {
        public let base: URL       // folder containing the exercise CSV
        public let exDir: URL      // jsons/com.samsung.health.exercise
        public let csv: URL
    }

    public enum ExportError: Error, CustomStringConvertible {
        case notFound
        public var description: String {
            "Couldn't find Samsung workout data. Expected a "
            + "'com.samsung.health.exercise.*.csv' and a 'jsons/' folder."
        }
    }

    /// Find the CSV and the exercise JSON dir under `base` (searching nested
    /// dirs). Ports `resolve_export` + `find_paths`.
    public static func resolve(_ base: URL) throws -> Root {
        let fm = FileManager.default

        func findCSV(_ dir: URL) -> URL? {
            guard let en = fm.enumerator(at: dir, includingPropertiesForKeys: nil) else { return nil }
            for case let u as URL in en {
                let n = u.lastPathComponent
                if n.hasPrefix("com.samsung.health.exercise"), n.hasSuffix(".csv") { return u }
            }
            return nil
        }
        func findExDir(_ dir: URL) -> URL? {
            let direct = dir.appendingPathComponent("jsons/com.samsung.health.exercise")
            var isDir: ObjCBool = false
            if fm.fileExists(atPath: direct.path, isDirectory: &isDir), isDir.boolValue { return direct }
            guard let en = fm.enumerator(at: dir, includingPropertiesForKeys: [.isDirectoryKey]) else { return nil }
            for case let u as URL in en where u.lastPathComponent == "com.samsung.health.exercise" {
                if (try? u.resourceValues(forKeys: [.isDirectoryKey]))?.isDirectory == true { return u }
            }
            return nil
        }

        guard let csv = findCSV(base), let exDir = findExDir(base) else {
            throw ExportError.notFound
        }
        return Root(base: csv.deletingLastPathComponent(), exDir: exDir, csv: csv)
    }

    /// Parse the CSV into workouts, newest-first. Port of `load_workouts`.
    public static func loadWorkouts(root: Root) -> [Workout] {
        guard let text = try? String(contentsOf: root.csv, encoding: .utf8) else { return [] }
        var items: [Workout] = []
        for row in CSV.dictRows(text) {
            guard let exId = row["datauuid"], !exId.isEmpty else { continue }
            let code = Int(fnum(row["exercise_type"]) ?? 0)
            let durS = (fnum(row["duration"]) ?? 0) / 1000.0
            let distM = fnum(row["distance"]) ?? 0.0
            let hr = fnum(row["mean_heart_rate"])
            let offset = fnum(row["time_offset"]) ?? 0
            let start = parseCSVDatetime(row["start_time"], offsetMs: offset)
            let hasGPS = !((row["location_data"] ?? "").trimmingCharacters(in: .whitespaces).isEmpty)
            items.append(Workout(
                id: exId, row: row, code: code, label: Labels.label(for: code),
                startMs: start, durationSeconds: durS, distanceMeters: distM,
                avgHR: hr, hasGPS: hasGPS))
        }
        items.sort { ($0.startMs ?? 0) > ($1.startMs ?? 0) }
        return items
    }

    /// Distinct sport labels present, for a filter dropdown. Port of `sport_labels`.
    public static func sportLabels(_ items: [Workout]) -> [String] {
        Array(Set(items.map { $0.label })).sorted()
    }
}
