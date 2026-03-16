import axios from "axios";
import { useRef, useState } from "react";

import { extractDocuments } from "../api/documents";
import { verifyEligibility } from "../api/verification";
import ErrorBanner from "../components/ErrorBanner";
import ExtractionReviewForm from "../components/ExtractionReviewForm";
import FileUploadSection from "../components/FileUploadSection";
import JsonSummaryViewer from "../components/JsonSummaryViewer";
import Layout from "../components/Layout";
import LoadingSpinner from "../components/LoadingSpinner";
import Raw271Viewer from "../components/Raw271Viewer";
import VerificationSummary from "../components/VerificationSummary";
import WarningList from "../components/WarningList";
import type {
  ExtractionResponse,
  ReviewFormValues,
  SelectedDocuments,
  VerificationRequest,
  VerificationResponse,
} from "../types/api";
import { EMPTY_REVIEW_FORM, INITIAL_SELECTED_DOCUMENTS } from "../utils/constants";

function createEmptyReviewForm(): ReviewFormValues {
  return { ...EMPTY_REVIEW_FORM };
}

function buildReviewFormValues(
  extractionResponse: ExtractionResponse,
): ReviewFormValues {
  return {
    ...extractionResponse.patient,
    ...extractionResponse.insurance,
  };
}

function buildVerificationRequest(
  values: ReviewFormValues,
): VerificationRequest {
  return {
    patient: {
      firstName: values.firstName,
      middleName: values.middleName,
      lastName: values.lastName,
      dateOfBirth: values.dateOfBirth,
      address: values.address,
      city: values.city,
      state: values.state,
      postalCode: values.postalCode,
    },
    insurance: {
      payerName: values.payerName,
      payerId: values.payerId,
      memberId: values.memberId,
      groupNumber: values.groupNumber,
      rxBin: values.rxBin,
      rxPcn: values.rxPcn,
      rxGroup: values.rxGroup,
      memberPhone: values.memberPhone,
      providerPhone: values.providerPhone,
      providerWebsite: values.providerWebsite,
      pharmacyPhone: values.pharmacyPhone,
      pharmacyClaimsAddress: values.pharmacyClaimsAddress,
    },
  };
}

function buildExtractionFormData(selectedDocuments: SelectedDocuments): FormData {
  const formData = new FormData();

  formData.append(
    "driver_license",
    selectedDocuments.driversLicense as Blob,
    selectedDocuments.driversLicense?.name,
  );
  formData.append(
    "insurance_front",
    selectedDocuments.insuranceFront as Blob,
    selectedDocuments.insuranceFront?.name,
  );
  formData.append(
    "insurance_back",
    selectedDocuments.insuranceBack as Blob,
    selectedDocuments.insuranceBack?.name,
  );

  return formData;
}

function getErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    return (
      (typeof error.response?.data?.detail === "string"
        ? error.response.data.detail
        : undefined) ??
      error.message ??
      fallback
    );
  }

  if (error instanceof Error) {
    return error.message;
  }

  return fallback;
}

export default function HomePage() {
  const [selectedDocuments, setSelectedDocuments] = useState<SelectedDocuments>(
    INITIAL_SELECTED_DOCUMENTS,
  );
  const [formValues, setFormValues] = useState<ReviewFormValues>(
    createEmptyReviewForm,
  );
  const [extractionResponse, setExtractionResponse] =
    useState<ExtractionResponse | null>(null);
  const [verificationResponse, setVerificationResponse] =
    useState<VerificationResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isExtracting, setIsExtracting] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);

  const extractRequestRef = useRef(0);
  const verifyRequestRef = useRef(0);

  function resetDownstreamState() {
    extractRequestRef.current += 1;
    verifyRequestRef.current += 1;

    setIsExtracting(false);
    setIsVerifying(false);
    setExtractionResponse(null);
    setVerificationResponse(null);
    setFormValues(createEmptyReviewForm());
  }

  function handleFileChange(
    documentKind: keyof SelectedDocuments,
    file: File | null,
  ) {
    setSelectedDocuments((current) => ({
      ...current,
      [documentKind]: file,
    }));
    setErrorMessage(null);
    resetDownstreamState();
  }

  function handleFormChange(field: keyof ReviewFormValues, value: string) {
    setFormValues((current) => ({
      ...current,
      [field]: value,
    }));
    setErrorMessage(null);
    setVerificationResponse(null);
  }

  async function handleExtract() {
    const hasAllDocuments = Object.values(selectedDocuments).every(Boolean);

    if (!hasAllDocuments) {
      setErrorMessage("Please select all three document images before extracting.");
      return;
    }

    const requestId = extractRequestRef.current + 1;
    extractRequestRef.current = requestId;
    verifyRequestRef.current += 1;

    setErrorMessage(null);
    setIsExtracting(true);
    setIsVerifying(false);
    setVerificationResponse(null);

    try {
      const response = await extractDocuments(
        buildExtractionFormData(selectedDocuments),
      );

      if (extractRequestRef.current !== requestId) {
        return;
      }

      setExtractionResponse(response);
      setFormValues(buildReviewFormValues(response));
    } catch (error) {
      if (extractRequestRef.current !== requestId) {
        return;
      }

      setErrorMessage(
        getErrorMessage(error, "Unable to extract documents right now."),
      );
    } finally {
      if (extractRequestRef.current === requestId) {
        setIsExtracting(false);
      }
    }
  }

  async function handleVerify() {
    if (!extractionResponse) {
      setErrorMessage("Run extraction before verifying eligibility.");
      return;
    }

    const requestId = verifyRequestRef.current + 1;
    verifyRequestRef.current = requestId;

    setErrorMessage(null);
    setIsVerifying(true);
    setVerificationResponse(null);

    try {
      const response = await verifyEligibility(
        buildVerificationRequest(formValues),
      );

      if (verifyRequestRef.current !== requestId) {
        return;
      }

      setVerificationResponse(response);
    } catch (error) {
      if (verifyRequestRef.current !== requestId) {
        return;
      }

      setErrorMessage(
        getErrorMessage(error, "Unable to verify eligibility right now."),
      );
    } finally {
      if (verifyRequestRef.current === requestId) {
        setIsVerifying(false);
      }
    }
  }

  const canExtract = Object.values(selectedDocuments).every(Boolean);

  return (
    <Layout
      subtitle="A working intake flow for document upload, extraction review, and live prototype eligibility verification."
      title="Patient Eligibility Prototype"
    >
      <div className="page-grid">
        {errorMessage ? <ErrorBanner message={errorMessage} /> : null}

        <section className="panel">
          <div className="panel__header">
            <span className="panel__step">01</span>
            <div>
              <h2>Upload Documents</h2>
              <p>
                Stage the driver&apos;s license plus the insurance card front and back to
                kick off backend extraction.
              </p>
            </div>
          </div>

          <FileUploadSection
            canExtract={canExtract}
            isExtracting={isExtracting}
            onExtract={handleExtract}
            onFileChange={handleFileChange}
            selectedDocuments={selectedDocuments}
          />

          {isExtracting ? (
            <LoadingSpinner label="Extracting document data..." />
          ) : null}

          {extractionResponse ? (
            <p className="panel__note">
              Extraction confidence:{" "}
              {Math.round(extractionResponse.confidence * 100)}%{" "}
              <span className="panel__note-divider">/</span>{" "}
              {extractionResponse.documentNotes.join(" / ")}
            </p>
          ) : (
            <p className="panel__note">
              Upload all three images, then click Extract to populate the review form.
            </p>
          )}
        </section>

        <section className="panel">
          <div className="panel__header">
            <span className="panel__step">02</span>
            <div>
              <h2>Review Extracted Data</h2>
              <p>
                Correct patient demographics and insurance fields before sending
                a verification request.
              </p>
            </div>
          </div>

          <ExtractionReviewForm
            disabled={!extractionResponse}
            isVerifying={isVerifying}
            onChange={handleFormChange}
            onVerify={handleVerify}
            values={formValues}
          />

          {isVerifying ? (
            <LoadingSpinner label="Verifying eligibility and parsing 271..." />
          ) : null}

          <article className="summary-card">
            <h3>Extraction Warnings</h3>
            <WarningList
              emptyMessage="Extraction warnings will appear here after the documents are processed."
              warnings={extractionResponse?.warnings ?? []}
            />
          </article>
        </section>

        <section className="panel">
          <div className="panel__header">
            <span className="panel__step">03</span>
            <div>
              <h2>Front-Desk Summary</h2>
              <p>
                Surface coverage, copays, pharmacy routing, warnings, and raw
                271 output for the intake team.
              </p>
            </div>
          </div>

          <VerificationSummary
            checkedAt={verificationResponse?.checkedAt ?? null}
            summary={verificationResponse?.summary ?? null}
          />

          <div className="summary-subgrid">
            <article className="summary-card">
              <h3>Warnings</h3>
              <WarningList
                emptyMessage="Verification warnings will appear here after eligibility is checked."
                warnings={verificationResponse?.warnings ?? []}
              />
            </article>

            <article className="summary-card">
              <h3>Raw 271</h3>
              <Raw271Viewer raw271={verificationResponse?.raw271 ?? null} />
            </article>
          </div>

          <article className="summary-card">
            <h3>Structured JSON Summary</h3>
            <JsonSummaryViewer
              summary={verificationResponse?.summary ?? null}
            />
          </article>
        </section>
      </div>
    </Layout>
  );
}
