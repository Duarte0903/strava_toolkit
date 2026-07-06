import SwiftUI
import UniformTypeIdentifiers
import StravaToolkitKit

struct ContentView: View {
    @EnvironmentObject var model: AppModel
    @State private var showImporter = false

    var body: some View {
        NavigationStack {
            Group {
                if model.isLoaded {
                    WorkoutListView()
                } else {
                    ImportPrompt(showImporter: $showImporter)
                }
            }
            .overlay {
                if model.isLoading { LoadingOverlay() }
            }
            .animation(.easeInOut(duration: 0.2), value: model.isLoading)
            .navigationTitle("Samsung → Strava")
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button("Open export…") { showImporter = true }
                }
            }
            .fileImporter(isPresented: $showImporter,
                          allowedContentTypes: [.zip],
                          allowsMultipleSelection: false) { result in
                if case let .success(urls) = result, let url = urls.first {
                    model.importZip(url)
                }
            }
            .alert("Couldn't open export",
                   isPresented: Binding(get: { model.importError != nil },
                                        set: { if !$0 { model.importError = nil } })) {
                Button("OK", role: .cancel) {}
            } message: { Text(model.importError ?? "") }
        }
        .tint(Theme.accent)
    }
}

private struct LoadingOverlay: View {
    var body: some View {
        ZStack {
            Color.black.opacity(0.25).ignoresSafeArea()
            VStack(spacing: 14) {
                ProgressView()
                    .controlSize(.large)
                    .tint(Theme.accent)
                Text("Reading export…")
                    .font(.subheadline).foregroundStyle(.secondary)
            }
            .padding(28)
            .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 16))
        }
        .transition(.opacity)
    }
}

private struct ImportPrompt: View {
    @Binding var showImporter: Bool
    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "square.and.arrow.down.on.square")
                .font(.system(size: 52)).foregroundStyle(Theme.accent)
            Text("Import a Samsung Health export")
                .font(.title3).bold()
            Text("Pick the export .zip. Workouts you export are saved into Files → On My iPhone → StravaToolkit, ready to upload at strava.com.")
                .font(.subheadline).foregroundStyle(.secondary)
                .multilineTextAlignment(.center).padding(.horizontal, 32)
            Button("Choose .zip") { showImporter = true }
                .buttonStyle(.borderedProminent).tint(Theme.accent)
        }
    }
}
