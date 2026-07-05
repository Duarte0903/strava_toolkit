import Foundation

/// Remembers which workouts have already been exported, as an id -> date map
/// (Samsung datauuids are globally unique). Port of the desktop `export_log.py`.
///
/// GUI-free; every call takes an explicit `path` (defaulting to Application
/// Support) so it can be tested against a temp file.
public enum ExportLog {

    /// `Library/Application Support/exported.json`.
    public static func defaultURL() -> URL {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        return base.appendingPathComponent("exported.json")
    }

    /// Load the map. Missing/unreadable/corrupt file -> [:] (never throws).
    public static func load(path: URL) -> [String: String] {
        guard let data = try? Data(contentsOf: path),
              let obj = try? JSONSerialization.jsonObject(with: data),
              let dict = obj as? [String: String]
        else { return [:] }
        return dict
    }

    /// Merge `ids` into the log with today's date (yyyy-MM-dd), writing back
    /// atomically. Creates the parent dir; re-marking refreshes the date.
    /// Returns the updated map.
    @discardableResult
    public static func mark(_ ids: [String], path: URL) throws -> [String: String] {
        var log = load(path: path)
        let today = todayString()
        for id in ids { log[id] = today }

        let dir = path.deletingLastPathComponent()
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let data = try JSONSerialization.data(withJSONObject: log,
                                              options: [.prettyPrinted, .sortedKeys])
        let fm = FileManager.default
        if fm.fileExists(atPath: path.path) {
            let tmp = dir.appendingPathComponent(".exported-\(UUID().uuidString).tmp")
            try data.write(to: tmp)
            _ = try fm.replaceItemAt(path, withItemAt: tmp)   // atomic replace
        } else {
            try data.write(to: path, options: .atomic)        // first write
        }
        return log
    }

    private static func todayString() -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(identifier: "UTC")
        f.dateFormat = "yyyy-MM-dd"
        return f.string(from: Date())
    }
}
