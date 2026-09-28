import type { paths } from "./generated/document-platform";

type UploadOperation = paths["/api/v1/documents"]["post"];
type WorkQueueOperation = paths["/api/v1/documents"]["get"];
type StatusOperation = paths["/api/v1/documents/{document_id}"]["get"];
type ReviewResolutionOperation =
    paths["/api/v1/documents/{document_id}/review-resolution"]["post"];
type ReprocessingOperation =
    paths["/api/v1/documents/{document_id}/reprocessing-requests"]["post"];

export type AcceptedDocument =
    UploadOperation["responses"][202]["content"]["application/json"];
export type DocumentWorkQueue =
    WorkQueueOperation["parameters"]["query"]["queue"];
export type DocumentWorkQueuePage =
    WorkQueueOperation["responses"][200]["content"]["application/json"];
export type DocumentStatus =
    StatusOperation["responses"][200]["content"]["application/json"];
export type ReviewResolutionRequest =
    ReviewResolutionOperation["requestBody"]["content"]["application/json"];
export type ReviewResolution =
    ReviewResolutionOperation["responses"][200]["content"]["application/json"];
export type DocumentReprocessingRequest =
    ReprocessingOperation["requestBody"]["content"]["application/json"];
export type DocumentReprocessing =
    ReprocessingOperation["responses"][202]["content"]["application/json"];
export type ProblemDetails =
    StatusOperation["responses"][404]["content"]["application/problem+json"];

export class DocumentApiProblem extends Error {
    constructor(readonly problem: ProblemDetails) {
        super(problem.detail);
        this.name = "DocumentApiProblem";
    }
}

export type DocumentApi = ReturnType<typeof createDocumentApi>;

export function createDocumentApi(fetcher: typeof fetch = globalThis.fetch) {
    return {
        async listWorkQueue(
            queue: DocumentWorkQueue,
            offset = 0,
            signal?: AbortSignal,
        ): Promise<DocumentWorkQueuePage> {
            const parameters = new URLSearchParams({
                queue,
                limit: "25",
                offset: String(offset),
            });
            const response = await fetcher(
                `/api/v1/documents?${parameters.toString()}`,
                { signal },
            );
            return readResponse<DocumentWorkQueuePage>(response);
        },

        async upload(
            document: File,
            idempotencyKey: string,
        ): Promise<AcceptedDocument> {
            const body = new FormData();
            body.append("document", document);
            const response = await fetcher("/api/v1/documents", {
                method: "POST",
                headers: { "Idempotency-Key": idempotencyKey },
                body,
            });
            return readResponse<AcceptedDocument>(response);
        },

        async getStatus(
            documentId: string,
            signal?: AbortSignal,
        ): Promise<DocumentStatus> {
            const response = await fetcher(
                `/api/v1/documents/${encodeURIComponent(documentId)}`,
                { signal },
            );
            return readResponse<DocumentStatus>(response);
        },

        async getSourceDocument(
            documentId: string,
            operatorToken: string,
            signal?: AbortSignal,
        ): Promise<Blob> {
            const response = await fetcher(
                `/api/v1/documents/${encodeURIComponent(documentId)}/source`,
                {
                    headers: { Authorization: `Bearer ${operatorToken}` },
                    signal,
                },
            );
            if (!response.ok) {
                return readResponse<Blob>(response);
            }
            return response.blob();
        },

        async resolveReview(
            documentId: string,
            resolution: ReviewResolutionRequest,
            operatorToken: string,
        ): Promise<ReviewResolution> {
            const response = await fetcher(
                `/api/v1/documents/${encodeURIComponent(documentId)}/review-resolution`,
                {
                    method: "POST",
                    headers: {
                        Authorization: `Bearer ${operatorToken}`,
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify(resolution),
                },
            );
            return readResponse<ReviewResolution>(response);
        },

        async requestReprocessing(
            documentId: string,
            reprocessing: DocumentReprocessingRequest,
            operatorToken: string,
            idempotencyKey: string,
        ): Promise<DocumentReprocessing> {
            const response = await fetcher(
                `/api/v1/documents/${encodeURIComponent(documentId)}/reprocessing-requests`,
                {
                    method: "POST",
                    headers: {
                        Authorization: `Bearer ${operatorToken}`,
                        "Content-Type": "application/json",
                        "Idempotency-Key": idempotencyKey,
                    },
                    body: JSON.stringify(reprocessing),
                },
            );
            return readResponse<DocumentReprocessing>(response);
        },
    };
}

async function readResponse<T>(response: Response): Promise<T> {
    if (response.ok) {
        return (await response.json()) as T;
    }

    if (
        response.headers
            .get("content-type")
            ?.includes("application/problem+json")
    ) {
        const body: unknown = await response.json();
        if (isProblemDetails(body)) {
            throw new DocumentApiProblem(body);
        }
    }

    throw new Error(
        `Document API request failed with status ${response.status}`,
    );
}

function isProblemDetails(value: unknown): value is ProblemDetails {
    if (typeof value !== "object" || value === null) {
        return false;
    }
    const candidate = value as Record<string, unknown>;
    return (
        typeof candidate.type === "string" &&
        typeof candidate.title === "string" &&
        typeof candidate.status === "number" &&
        typeof candidate.detail === "string"
    );
}
