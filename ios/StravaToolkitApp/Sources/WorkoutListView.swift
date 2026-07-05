import SwiftUI
import StravaToolkitKit

struct WorkoutListView: View {
    @EnvironmentObject var model: AppModel

    var body: some View {
        VStack(spacing: 0) {
            filters
            List {
                ForEach(model.filtered) { w in
                    NavigationLink { WorkoutDetailView(workout: w) } label: {
                        WorkoutRow(workout: w, selected: model.selection.contains(w.id))
                            .contentShape(Rectangle())
                    }
                    .swipeActions(edge: .leading) {
                        Button(model.selection.contains(w.id) ? "Deselect" : "Select") {
                            model.toggle(w.id)
                        }.tint(Theme.accent)
                    }
                }
            }
            .listStyle(.plain)
            exportBar
        }
    }

    private var filters: some View {
        VStack(spacing: 8) {
            HStack {
                Picker("Type", selection: $model.typeFilter) {
                    ForEach(model.sportLabels, id: \.self) { Text($0).tag($0) }
                }
                .pickerStyle(.menu)
                Spacer()
                Button("Select shown") { model.selectShown() }.font(.footnote)
                Button("Clear") { model.clearSelection() }.font(.footnote)
            }
            TextField("Search", text: $model.search)
                .textFieldStyle(.roundedBorder)
            TextField("Since (YYYY-MM-DD)", text: $model.sinceText)
                .textFieldStyle(.roundedBorder)
                .autocorrectionDisabled()
            Toggle("Hide exported", isOn: $model.hideExported)
                .font(.footnote)
                .tint(Theme.accent)
        }
        .padding(.horizontal).padding(.top, 8)
    }

    private var exportBar: some View {
        VStack(spacing: 8) {
            Picker("Format", selection: $model.format) {
                ForEach(ExportFormat.allCases, id: \.self) { Text($0.display).tag($0) }
            }
            .pickerStyle(.segmented)
            HStack {
                Text("\(model.selection.count) selected").foregroundStyle(.secondary)
                Spacer()
                Button("Export selected") { model.exportSelected() }
                    .buttonStyle(.borderedProminent).tint(Theme.accent)
                    .disabled(model.selection.isEmpty)
            }
            if !model.status.isEmpty {
                Text(model.status).font(.footnote).foregroundStyle(.secondary)
            }
        }
        .padding()
        .background(.bar)
        .alert(item: $model.lastExport) { s in
            Alert(title: Text("Exported \(s.made) files"),
                  message: Text("Saved to Files → On My iPhone → StravaToolkit → strava_upload.\nUpload them at strava.com/upload/select."),
                  dismissButton: .default(Text("OK")))
        }
    }
}

struct WorkoutRow: View {
    let workout: Workout
    let selected: Bool

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: selected ? "checkmark.circle.fill" : "circle")
                .foregroundStyle(selected ? Theme.accent : Color.secondary)
            VStack(alignment: .leading, spacing: 2) {
                Text("\(workout.label) · \(fmtDate(workout.startMs))").font(.body)
                Text("\(fmtDuration(workout.durationSeconds)) · \(fmtDistance(workout.distanceMeters))")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Spacer()
            if workout.hasGPS {
                Image(systemName: "location.fill").font(.caption2).foregroundStyle(.secondary)
            }
        }
        .padding(.vertical, 2)
    }
}
