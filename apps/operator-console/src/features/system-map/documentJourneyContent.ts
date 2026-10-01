export type JourneyId =
    "auto-approval" | "manual-review" | "failed-run" | "unsupported-document";

export type JourneyStep = {
    title: string;
    owner: string;
    description: string;
    state: string;
    referencePath: string;
};

export type Journey = {
    id: JourneyId;
    label: string;
    outcome: string;
    steps: readonly JourneyStep[];
};

const upload: JourneyStep = {
    title: "Accept PDF",
    owner: "Console / API / PostgreSQL",
    description:
        "The API commits the document, first run, idempotency result and pending workflow-start request together. PDF bytes are stored separately.",
    state: "Document UPLOADED · run QUEUED",
    referencePath:
        "src/document_platform/application/commands/accept_document_upload.py",
};

const handoff: JourneyStep = {
    title: "Dispatch after commit",
    owner: "Dispatcher / Temporal",
    description:
        "The dispatcher claims the committed request and starts a workflow with a stable ID. Temporal calls do not happen inside the upload transaction.",
    state: "Start request DISPATCHED",
    referencePath:
        "src/document_platform/application/commands/dispatch_workflow_start_requests.py",
};

const processing: JourneyStep = {
    title: "Start processing",
    owner: "Temporal / worker / PostgreSQL",
    description:
        "The worker starts the document and processing run atomically before executing the document activities.",
    state: "Document PROCESSING · run RUNNING",
    referencePath:
        "src/document_platform/workflows/process_business_document.py",
};

const extraction: JourneyStep = {
    title: "Select processing text",
    owner: "Worker / local blob volume",
    description:
        "Embedded text is persisted first. OCR runs only when quality recommends it; the chosen text source and reason are persisted per run.",
    state: "Immutable extraction and selection evidence",
    referencePath:
        "src/document_platform/application/commands/select_processing_text.py",
};

const classification: JourneyStep = {
    title: "Classify document",
    owner: "Worker / PostgreSQL",
    description:
        "A deterministic, versioned policy classifies the selected text. Only invoices continue through invoice extraction and validation; other types receive an explicit unsupported outcome.",
    state: "Persisted document type and reason",
    referencePath:
        "src/document_platform/application/commands/classify_document.py",
};

const aiProposal: JourneyStep = {
    title: "Suggest invoice fields (optional)",
    owner: "Worker / Ollama / PostgreSQL",
    description:
        "After deterministic processing, the worker can send the selected invoice text to a local model. A proposal or safe failure record is stored separately; the operator decides whether to use any suggested value.",
    state: "AI execution DISABLED, COMPLETED or FAILED; document outcome is independent",
    referencePath:
        "src/document_platform/application/commands/propose_invoice_fields.py",
};

const invoiceSteps = [upload, handoff, processing, extraction, classification];

export const journeys: readonly Journey[] = [
    {
        id: "auto-approval",
        label: "Auto-approved invoice",
        outcome: "A complete invoice passes deterministic validation.",
        steps: [
            ...invoiceSteps,
            {
                title: "Apply validation",
                owner: "Worker / PostgreSQL",
                description:
                    "Invoice fields and validation decision are persisted. An AUTO_APPROVE decision updates the document and run in one transaction.",
                state: "Document APPROVED · run COMPLETED",
                referencePath:
                    "src/document_platform/application/commands/apply_invoice_validation.py",
            },
            aiProposal,
        ],
    },
    {
        id: "manual-review",
        label: "Review-required invoice",
        outcome:
            "Invoice validation issues prevent automatic approval and require an operator decision.",
        steps: [
            ...invoiceSteps,
            {
                title: "Request review",
                owner: "Worker / PostgreSQL",
                description:
                    "A REVIEW_REQUIRED validation decision persists the need for operator review without inventing an approval.",
                state: "Document REVIEW_REQUIRED · run REVIEW_REQUIRED",
                referencePath:
                    "src/document_platform/application/commands/apply_invoice_validation.py",
            },
            aiProposal,
            {
                title: "Resolve review",
                owner: "Operator / API / PostgreSQL",
                description:
                    "The operator approves or rejects. Approval may include typed corrections; the original extraction remains immutable.",
                state: "Document APPROVED or REJECTED · run COMPLETED",
                referencePath:
                    "src/document_platform/application/commands/resolve_document_review.py",
            },
        ],
    },
    {
        id: "unsupported-document",
        label: "Unsupported document",
        outcome:
            "Unknown documents and recognized non-invoices finish with a visible unsupported outcome.",
        steps: [
            ...invoiceSteps,
            {
                title: "Complete as unsupported",
                owner: "Worker / PostgreSQL",
                description:
                    "The saved classification distinguishes unknown input from a recognized type without invoice extraction. The document status and completed run commit atomically.",
                state: "Document UNSUPPORTED · run COMPLETED",
                referencePath:
                    "src/document_platform/application/commands/complete_processing_run.py",
            },
        ],
    },
    {
        id: "failed-run",
        label: "Failure and reprocessing",
        outcome:
            "A terminal activity failure is recorded; a new run can be requested.",
        steps: [
            upload,
            handoff,
            processing,
            {
                title: "Record terminal failure",
                owner: "Temporal / worker / PostgreSQL",
                description:
                    "After bounded activity retries are exhausted, the failing stage and code are persisted. Temporal history remains failed.",
                state: "Document FAILED · run FAILED",
                referencePath:
                    "src/document_platform/application/commands/record_processing_run_failure.py",
            },
            {
                title: "Request a new run",
                owner: "Operator / API / PostgreSQL",
                description:
                    "Authenticated reprocessing creates a linked replacement run and pending start request. It does not erase the failed run or guarantee success.",
                state: "Replacement run QUEUED",
                referencePath:
                    "src/document_platform/application/commands/request_document_reprocessing.py",
            },
        ],
    },
];
