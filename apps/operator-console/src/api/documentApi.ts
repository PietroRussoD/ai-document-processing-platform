import type { paths } from "./generated/document-platform";

type UploadOperation = paths["/api/v1/documents"]["post"];
type StatusOperation = paths["/api/v1/documents/{document_id}"]["get"];
type ReviewResolutionOperation =
    paths["/api/v1/documents/{document_id}/review-resolution"]["post"];

export type AcceptedDocument =
    UploadOperation["responses"][202]["content"]["application/json"];
export type DocumentStatus =
    StatusOperation["responses"][200]["content"]["application/json"];
export type ReviewResolutionRequest =
    ReviewResolutionOperation["requestBody"]["content"]["application/json"];
export type ReviewResolution =
    ReviewResolutionOperation["responses"][200]["content"]["application/json"];
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
