import { PlaceholderPanel } from "./components/PlaceholderPanel";
import { HealthStatus } from "./features/health/HealthStatus";

function App() {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_#d5efe9,_#edf2f7_55%)] text-ink">
      <div className="mx-auto flex min-h-screen max-w-7xl flex-col px-6 py-8">
        <header className="mb-8 rounded-3xl border border-white/60 bg-white/70 p-6 shadow-sm backdrop-blur">
          <p className="text-sm uppercase tracking-[0.3em] text-tide">DrawAgent 2.0</p>
          <h1 className="mt-3 text-4xl font-semibold">Phase 1 Engineering Skeleton</h1>
          <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-600">
            This frontend is a Phase 1 placeholder shell. Conversation flow, LangGraph orchestration,
            session state, and image generation will be connected in later phases.
          </p>
          <div className="mt-6">
            <HealthStatus />
          </div>
        </header>

        <main className="grid flex-1 gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <PlaceholderPanel
            title="Conversation Workspace"
            description="Future home for chat input, attachments, clarification turns, and progress events."
          />
          <PlaceholderPanel
            title="Artifacts and Preview"
            description="Future home for logic/style/mapper payload summaries, final prompt preview, and generated images."
          />
        </main>
      </div>
    </div>
  );
}

export default App;
