import type { SelectedDocuments } from "../types/api";
import { DOCUMENT_FIELDS } from "../utils/constants";
import ImagePreview from "./ImagePreview";

interface FileUploadSectionProps {
  canExtract: boolean;
  selectedDocuments: SelectedDocuments;
  isExtracting: boolean;
  onFileChange: (
    documentKind: keyof SelectedDocuments,
    file: File | null,
  ) => void;
  onExtract: () => void;
}

export default function FileUploadSection({
  canExtract,
  selectedDocuments,
  isExtracting,
  onFileChange,
  onExtract,
}: FileUploadSectionProps) {
  return (
    <div className="panel__body panel__body--uploads">
      <div className="upload-grid">
        {DOCUMENT_FIELDS.map((field) => (
          <label className="upload-card" key={field.key}>
            <span className="upload-card__title">{field.label}</span>
            <span className="upload-card__helper">{field.helper}</span>

            <input
              accept={field.accept}
              className="upload-card__input"
              disabled={isExtracting}
              onChange={(event) =>
                onFileChange(field.key, event.target.files?.[0] ?? null)
              }
              type="file"
            />

            <span className="upload-card__filename">
              {selectedDocuments[field.key]?.name ?? "No file selected"}
            </span>
          </label>
        ))}
      </div>

      <div className="preview-grid">
        {DOCUMENT_FIELDS.map((field) => (
          <ImagePreview
            key={field.key}
            file={selectedDocuments[field.key]}
            label={field.label}
          />
        ))}
      </div>

      <div className="panel__actions panel__actions--uploads">
        <button
          className="button button--primary"
          disabled={isExtracting || !canExtract}
          onClick={onExtract}
          type="button"
        >
          {isExtracting ? "Extracting..." : "Extract"}
        </button>
      </div>
    </div>
  );
}
