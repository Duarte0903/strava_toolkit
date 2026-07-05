import Foundation

// Number / date / formatting helpers — ports of the small utilities in
// samsung_to_tcx.py and workout_core.py.

/// Coerce an arbitrary JSON/CSV value to a Double, mirroring Python's `fnum`.
public func fnum(_ v: Any?) -> Double? {
    switch v {
    case let d as Double: return d
    case let i as Int: return Double(i)
    case let n as NSNumber: return n.doubleValue
    case let s as String:
        let t = s.trimmingCharacters(in: .whitespaces)
        if t.isEmpty || t == "nan" { return nil }
        return Double(t)
    default:
        return nil
    }
}

private let utc = TimeZone(identifier: "UTC")!

/// Epoch-ms (UTC) -> "yyyy-MM-dd'T'HH:mm:ss'Z'" (port of `iso`).
public func iso(_ unixMs: Int) -> String {
    let f = DateFormatter()
    f.locale = Locale(identifier: "en_US_POSIX")
    f.timeZone = utc
    f.dateFormat = "yyyy-MM-dd'T'HH:mm:ss'Z'"
    return f.string(from: Date(timeIntervalSince1970: Double(unixMs) / 1000.0))
}

/// Parse the exercise CSV's local start-time string into epoch-ms (UTC),
/// removing the local `time_offset` so it lines up with live_data timestamps.
/// Port of `parse_csv_datetime`.
public func parseCSVDatetime(_ s: String?, offsetMs: Double = 0) -> Int? {
    guard let raw = s?.trimmingCharacters(in: .whitespaces), !raw.isEmpty else { return nil }
    let formats = ["dd/MM/yyyy, HH:mm:ss", "MM/dd/yyyy, HH:mm:ss", "yyyy-MM-dd HH:mm:ss"]
    for fmt in formats {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = utc
        f.dateFormat = fmt
        if let d = f.date(from: raw) {
            let localMs = Int(d.timeIntervalSince1970 * 1000)
            return localMs - Int(offsetMs)
        }
    }
    return nil
}

public func fmtDate(_ startMs: Int?) -> String {
    guard let ms = startMs else { return "—" }
    let f = DateFormatter()
    f.locale = Locale(identifier: "en_US_POSIX")
    f.timeZone = utc
    f.dateFormat = "yyyy-MM-dd HH:mm"
    return f.string(from: Date(timeIntervalSince1970: Double(ms) / 1000.0))
}

public func fmtDuration(_ sec: Double) -> String {
    let s = Int(sec.rounded(.towardZero))
    let h = s / 3600, m = (s % 3600) / 60, ss = s % 60
    return h > 0 ? String(format: "%d:%02d:%02d", h, m, ss)
                 : String(format: "%d:%02d", m, ss)
}

public func fmtDistance(_ m: Double) -> String {
    m > 0 ? String(format: "%.2f km", m / 1000.0) : "—"
}

public func fmtPace(_ sPerKm: Double?) -> String {
    guard let p = sPerKm, p > 0 else { return "—" }
    let s = Int(p.rounded())
    return String(format: "%d:%02d /km", s / 60, s % 60)
}

public func xmlEscape(_ s: String) -> String {
    s.replacingOccurrences(of: "&", with: "&amp;")
     .replacingOccurrences(of: "<", with: "&lt;")
     .replacingOccurrences(of: ">", with: "&gt;")
}

/// Filename for an exported workout — port of `_safe_name`.
public func safeName(startMs: Int?, label: String, exId: String, ext: String) -> String {
    let f = DateFormatter()
    f.locale = Locale(identifier: "en_US_POSIX")
    f.timeZone = utc
    f.dateFormat = "yyyy-MM-dd_HHmm"
    let day = f.string(from: Date(timeIntervalSince1970: Double(startMs ?? 0) / 1000.0))
    let id8 = String(exId.prefix(8))
    return "\(day)_\(label)_\(id8).\(ext)"
}
