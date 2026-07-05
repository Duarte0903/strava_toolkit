import Foundation

// Loading Samsung's per-workout series files (live_data / location_data).
// Each file is a JSON array of objects; some are gzip-compressed.

public enum SeriesJSON {
    /// Load and decode a series JSON file (gzip-sniffed). Returns [] on any error.
    public static func load(_ url: URL) -> [[String: Any]] {
        guard let raw = try? Data(contentsOf: url) else { return [] }
        let data = Inflate.maybeGunzip(raw)
        let obj = try? JSONSerialization.jsonObject(with: data)
        return (obj as? [[String: Any]]) ?? []
    }

    /// Resolve `<ref>.json` inside the exercise dir and load it. Port of `_load`.
    public static func load(exDir: URL, ref: String?) -> [[String: Any]] {
        let r = (ref ?? "").trimmingCharacters(in: .whitespaces)
        guard !r.isEmpty else { return [] }
        let url = exDir.appendingPathComponent(r + ".json")
        guard FileManager.default.fileExists(atPath: url.path) else { return [] }
        return load(url)
    }
}
