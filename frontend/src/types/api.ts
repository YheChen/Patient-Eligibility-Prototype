export type DocumentKind =
  | "driversLicense"
  | "insuranceFront"
  | "insuranceBack";

export type WarningSeverity = "info" | "warning" | "critical";
export type VerificationStatus = "verified" | "pending" | "manual_review";
export type CoverageStatus = "active" | "inactive" | "unknown";

export interface Patient {
  firstName: string;
  middleName: string;
  lastName: string;
  dateOfBirth: string;
  address: string;
  city: string;
  state: string;
  postalCode: string;
}

export interface Insurance {
  payerName: string;
  payerId: string;
  memberId: string;
  groupNumber: string;
  rxBin: string;
  rxPcn: string;
  rxGroup: string;
  memberPhone: string;
  providerPhone: string;
  providerWebsite: string;
  pharmacyPhone: string;
  pharmacyClaimsAddress: string;
}

export interface Warning {
  code: string;
  message: string;
  severity: WarningSeverity;
}

export interface Discrepancy {
  field: string;
  extractedValue: string;
  verifiedValue: string;
  note: string;
}

export interface ExtractionResponse {
  patient: Patient;
  insurance: Insurance;
  confidence: number;
  documentNotes: string[];
  missingFields: string[];
  warnings: Warning[];
}

export interface CopaySummary {
  primaryCare: string;
  specialist: string;
  urgentCare: string;
  pharmacy: string;
}

export interface PharmacyInfo {
  bin: string;
  pcn: string;
  group: string;
  processor: string;
}

export interface VerificationSummary {
  verificationStatus: VerificationStatus;
  coverageStatus: CoverageStatus;
  payerName: string;
  memberId: string;
  copays: CopaySummary;
  pharmacyInfo: PharmacyInfo;
  discrepancies: Discrepancy[];
}

export interface VerificationResponse {
  summary: VerificationSummary;
  warnings: Warning[];
  raw271: string;
  checkedAt: string;
}

export interface VerificationRequest {
  patient: Patient;
  insurance: Insurance;
}

export interface ReviewFormValues extends Patient, Insurance {}

export interface SelectedDocuments {
  driversLicense: File | null;
  insuranceFront: File | null;
  insuranceBack: File | null;
}
