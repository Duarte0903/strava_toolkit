import Foundation

// Minimal RFC-4180-ish CSV reader — the equivalent of Python's csv.DictReader,
// including Samsung's habit of prefixing the file with a junk first line.

public enum CSV {
    /// Parse rows of fields, honouring quoted fields (which may contain commas
    /// and newlines) and doubled-quote escapes.
    static func rows(_ text: String) -> [[String]] {
        var rows: [[String]] = []
        var field = ""
        var record: [String] = []
        var inQuotes = false
        let chars = Array(text)
        var i = 0
        func endField() { record.append(field); field = "" }
        func endRecord() { endField(); rows.append(record); record = [] }
        while i < chars.count {
            let c = chars[i]
            if inQuotes {
                if c == "\"" {
                    if i + 1 < chars.count && chars[i + 1] == "\"" { field.append("\""); i += 1 }
                    else { inQuotes = false }
                } else { field.append(c) }
            } else {
                switch c {
                case "\"": inQuotes = true
                case ",": endField()
                case "\r": break
                case "\n": endRecord()
                default: field.append(c)
                }
            }
            i += 1
        }
        // trailing field/record if the file doesn't end in a newline
        if !field.isEmpty || !record.isEmpty { endRecord() }
        return rows
    }

    /// Yield dict rows keyed by header. Skips Samsung's junk first line
    /// ("com.samsung…") when present. Port of `read_exercise_csv`.
    public static func dictRows(_ text: String) -> [[String: String]] {
        var rows = Self.rows(text).filter { !($0.count == 1 && $0[0].isEmpty) }
        guard !rows.isEmpty else { return [] }
        if let first = rows.first?.first,
           first.lowercased().hasPrefix("com.samsung") {
            rows.removeFirst()
        }
        guard let header = rows.first else { return [] }
        var out: [[String: String]] = []
        for r in rows.dropFirst() {
            var dict: [String: String] = [:]
            for (idx, key) in header.enumerated() {
                dict[key] = idx < r.count ? r[idx] : ""
            }
            out.append(dict)
        }
        return out
    }
}
