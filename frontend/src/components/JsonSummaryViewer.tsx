import type { VerificationSummary } from "../types/api";

interface JsonSummaryViewerProps {
  summary: VerificationSummary | null;
}

export default function JsonSummaryViewer({
  summary,
}: JsonSummaryViewerProps) {
  if (!summary) {
    return (
      <div className="empty-state">
        The structured JSON summary returned by <code>POST /api/verification/verify</code>{" "}
        will appear here after eligibility is checked.
      </div>
    );
  }

  return (
    <div className="json-viewer">
      <p className="json-viewer__note">
        Returned by <code>POST /api/verification/verify</code> as the{" "}
        <code>summary</code> object.
      </p>
      <pre>{JSON.stringify(summary, null, 2)}</pre>
    </div>
  );
}
