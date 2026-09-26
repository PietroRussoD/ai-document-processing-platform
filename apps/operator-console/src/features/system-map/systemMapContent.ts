export type SystemNodeId =
    | "console"
    | "api"
    | "postgres"
    | "dispatcher"
    | "temporal"
    | "worker"
    | "blob"
    | "extractors"
    | "observability";

export type SystemNode = {
    id: SystemNodeId;
    title: string;
    summary: string;
    receives: string;
    produces: string;
    referencePath: string;
    optional?: boolean;
};

export const processingPath: readonly SystemNodeId[] = [
    "console",
    "api",
    "postgres",
    "dispatcher",
    "temporal",
    "worker",
];

export const supportingNodes: readonly SystemNodeId[] = [
    "blob",
    "extractors",
    "observability",
];

export const systemNodes: Record<SystemNodeId, SystemNode> = {
    console: {
        id: "console",
        title: "Operator console",
        summary: "React UI served by NGINX",
        receives: "Operator actions and document status from the API",
        produces: "HTTP requests through the /api proxy",
        referencePath: "apps/operator-console/nginx.conf",
    },
    api: {
        id: "api",
        title: "FastAPI",
        summary: "Upload and operator HTTP boundary",
        receives: "Bounded PDF uploads and operator requests",
        produces:
            "Stored PDFs and committed document, run and start-request records",
        referencePath:
            "src/document_platform/application/commands/accept_document_upload.py",
    },
    postgres: {
        id: "postgres",
        title: "PostgreSQL",
        summary: "Authority for business state",
        receives: "Document, run, handoff and processing-output writes",
        produces: "Pending start requests and status projections",
        referencePath: "docs/architecture.md#persistence-model",
    },
    dispatcher: {
        id: "dispatcher",
        title: "Dispatcher",
        summary: "Post-commit workflow handoff",
        receives: "Committed pending start requests from PostgreSQL",
        produces: "Deterministic workflow starts in Temporal",
        referencePath: "src/document_platform/dispatcher.py",
    },
    temporal: {
        id: "temporal",
        title: "Temporal",
        summary: "Durable workflow execution",
        receives: "Workflow starts from the dispatcher",
        produces: "Scheduled activities and execution history",
        referencePath:
            "src/document_platform/workflows/process_business_document.py",
    },
    worker: {
        id: "worker",
        title: "Worker",
        summary: "Document-processing activities",
        receives: "Temporal activities and PDF bytes from local storage",
        produces: "Persisted extraction, validation and outcome records",
        referencePath: "src/document_platform/worker.py",
    },
    blob: {
        id: "blob",
        title: "Local blob volume",
        summary: "Immutable uploaded PDF bytes",
        receives: "Validated PDF from the API",
        produces: "Document bytes for worker activities",
        referencePath: "docs/architecture.md#local-blob-lifecycle",
    },
    extractors: {
        id: "extractors",
        title: "PDF extraction",
        summary: "PyMuPDF and bounded Tesseract OCR",
        receives: "PDF bytes from the worker",
        produces: "Embedded text and optional OCR text for persisted selection",
        referencePath: "docs/architecture.md#durable-workflow-handoff",
    },
    observability: {
        id: "observability",
        title: "Observability",
        summary: "Optional Prometheus and Grafana profile",
        receives: "Prometheus scrapes API metrics; Grafana queries Prometheus",
        produces: "Local operational dashboards, not document status authority",
        referencePath:
            "docs/decisions/0004-expose-low-cardinality-prometheus-metrics.md",
        optional: true,
    },
};
