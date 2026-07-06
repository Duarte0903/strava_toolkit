import Foundation
import StravaToolkitKit

/// Holds imported workouts and drives import/filter/export. All UI-facing state.
@MainActor
final class AppModel: ObservableObject {
    @Published var workouts: [Workout] = []
    @Published var selection: Set<String> = []
    @Published var format: ExportFormat = .auto

    // filters
    @Published var typeFilter = "All"
    @Published var search = ""
    @Published var sinceText = ""
    @Published var hideExported = false

    @Published var status = ""
    @Published var isLoading = false
    @Published var importError: String?
    @Published var lastExport: ExportSummary?

    private var exDir: URL?
    private let logURL = ExportLog.defaultURL()
    private var exported: [String: String] = [:]

    init() { exported = ExportLog.load(path: logURL) }

    func isExported(_ id: String) -> Bool { exported[id] != nil }

    struct ExportSummary: Identifiable {
        let id = UUID()
        let made: Int
        let skipped: Int
        let folder: URL
    }

    var isLoaded: Bool { !workouts.isEmpty }
    var sportLabels: [String] { ["All"] + SamsungExport.sportLabels(workouts) }

    var filtered: [Workout] {
        let sinceMs = parseSince()
        let q = search.trimmingCharacters(in: .whitespaces).lowercased()
        return workouts.filter { w in
            if typeFilter != "All", w.label != typeFilter { return false }
            if hideExported, exported[w.id] != nil { return false }
            if let sinceMs, (w.startMs ?? 0) < sinceMs { return false }
            if !q.isEmpty {
                let hay = (fmtDate(w.startMs) + " " + w.label).lowercased()
                if !hay.contains(q) { return false }
            }
            return true
        }
    }

    private func parseSince() -> Int? {
        let s = sinceText.trimmingCharacters(in: .whitespaces)
        guard !s.isEmpty else { return nil }
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(identifier: "UTC")
        f.dateFormat = "yyyy-MM-dd"
        guard let d = f.date(from: s) else { return nil }
        return Int(d.timeIntervalSince1970 * 1000)
    }

    func detail(for w: Workout) -> WorkoutDetail? {
        guard let exDir else { return nil }
        return WorkoutDetailLoader.load(exDir: exDir, workout: w)
    }

    // MARK: import

    private struct ParsedExport { let exDir: URL; let items: [Workout] }

    /// Import a Samsung export .zip: unzip into a temp dir, then parse. The
    /// unzip/parse runs off the main thread so the UI can show a spinner.
    func importZip(_ url: URL) {
        importError = nil
        isLoading = true
        status = "Loading…"
        Task {
            do {
                let parsed = try await Self.parseExport(url)
                self.exDir = parsed.exDir
                self.workouts = parsed.items
                self.selection = []
                self.typeFilter = "All"
                self.status = "Loaded \(parsed.items.count) workouts."
            } catch {
                self.importError = "\(error)"
                self.status = ""
            }
            self.isLoading = false
        }
    }

    /// The heavy lifting: unzip and parse the export off the main actor.
    private nonisolated static func parseExport(_ url: URL) async throws -> ParsedExport {
        try await Task.detached(priority: .userInitiated) {
            let scoped = url.startAccessingSecurityScopedResource()
            defer { if scoped { url.stopAccessingSecurityScopedResource() } }
            let tmp = URL(fileURLWithPath: NSTemporaryDirectory())
                .appendingPathComponent("samsung-export-\(UUID().uuidString)")
            try ZipReader.unzip(url, to: tmp)
            let root = try SamsungExport.resolve(tmp)
            let items = SamsungExport.loadWorkouts(root: root)
            return ParsedExport(exDir: root.exDir, items: items)
        }.value
    }

    // MARK: selection helpers

    func toggle(_ id: String) {
        if selection.contains(id) { selection.remove(id) } else { selection.insert(id) }
    }
    func selectShown() { filtered.forEach { selection.insert($0.id) } }
    func clearSelection() { selection.removeAll() }

    // MARK: export

    /// Export selected workouts into the app's Documents directory (visible in Files).
    func exportSelected() {
        guard let exDir else { return }
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        let outDir = docs.appendingPathComponent("strava_upload")
        try? FileManager.default.createDirectory(at: outDir, withIntermediateDirectories: true)

        let byId = Dictionary(uniqueKeysWithValues: workouts.map { ($0.id, $0) })
        let chosen = selection.compactMap { byId[$0] }
        var made = 0, skipped = 0
        var madeIds: [String] = []
        for w in chosen {
            do {
                let out = try Exporter.export(exDir: exDir, workout: w, format: format)
                try out.data.write(to: outDir.appendingPathComponent(out.filename))
                made += 1
                madeIds.append(w.id)
            } catch {
                skipped += 1
            }
        }
        // Remember what actually produced a file, so "Hide exported" can filter it.
        if !madeIds.isEmpty {
            for id in madeIds { exported[id] = "" }          // keep session correct even if the write fails
            if let updated = try? ExportLog.mark(madeIds, path: logURL) { exported = updated }
        }
        status = "Exported \(made) files (\(skipped) skipped)."
        lastExport = ExportSummary(made: made, skipped: skipped, folder: outDir)
    }
}
