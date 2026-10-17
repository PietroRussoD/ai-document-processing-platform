import { expect, test, vi } from "vitest";

import {
    createDocumentApi,
    DocumentApiProblem,
    DocumentApiHttpError,
} from "./documentApi";

const acceptedDocument = {
    document_id: "11111111-1111-4111-8111-111111111111",
    processing_run_id: "22222222-2222-4222-8222-222222222222",
    accepted_at: "2026-09-14T19:00:00Z",
    replayed: false,
};
const operatorToken = "operator-token";

test("lists a bounded document work queue and forwards cancellation", async () => {
    const page = { items: [], total: 0, limit: 25, offset: 0 } as const;
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(page));
    const controller = new AbortController();

    const result = await createDocumentApi(fetcher).listWorkQueue(
        "FAILED",
        operatorToken,
        25,
        controller.signal,
    );

    expect(result).toEqual(page);
    expect(fetcher).toHaveBeenCalledWith(
        "/api/v1/documents?queue=FAILED&limit=25&offset=25",
        {
            headers: { Authorization: `Bearer ${operatorToken}` },
            signal: controller.signal,
        },
    );
});

test("uploads a PDF as multipart data with its idempotency key", async () => {
    const fetcher = vi
        .fn<typeof fetch>()
        .mockResolvedValue(jsonResponse(acceptedDocument, 202));
    const document = new File(["pdf"], "invoice.pdf", {
        type: "application/pdf",
    });

    const result = await createDocumentApi(fetcher).upload(
        document,
        "upload-42",
        operatorToken,
    );

    expect(result).toEqual(acceptedDocument);
    expect(fetcher).toHaveBeenCalledOnce();
    const [url, request] = fetcher.mock.calls[0];
    expect(url).toBe("/api/v1/documents");
    expect(request?.method).toBe("POST");
    expect(request?.headers).toEqual({
        Authorization: `Bearer ${operatorToken}`,
        "Idempotency-Key": "upload-42",
    });
    expect(request?.body).toBeInstanceOf(FormData);
    expect((request?.body as FormData).get("document")).toBe(document);
});

test("retrieves document status and forwards cancellation", async () => {
    const status = {
        id: acceptedDocument.document_id,
        original_filename: "invoice.pdf",
        media_type: "application/pdf",
        size_bytes: 3,
        page_count: 1,
        content_sha256: "a".repeat(64),
        status: "UPLOADED",
        accepted_at: acceptedDocument.accepted_at,
        status_changed_at: acceptedDocument.accepted_at,
        current_run: {
            id: acceptedDocument.processing_run_id,
            status: "QUEUED",
            queued_at: acceptedDocument.accepted_at,
            started_at: null,
            status_changed_at: acceptedDocument.accepted_at,
            finished_at: null,
            attempt_count: 0,
            failure: null,
            processing_output: null,
            review_resolution: null,
        },
    } as const;
    const fetcher = vi
        .fn<typeof fetch>()
        .mockResolvedValue(jsonResponse(status));
    const controller = new AbortController();

    const result = await createDocumentApi(fetcher).getStatus(
        acceptedDocument.document_id,
        operatorToken,
        controller.signal,
    );

    expect(result).toEqual(status);
    expect(fetcher).toHaveBeenCalledWith(
        `/api/v1/documents/${acceptedDocument.document_id}`,
        {
            headers: { Authorization: `Bearer ${operatorToken}` },
            signal: controller.signal,
        },
    );
});

test("retrieves the source PDF with the operator token and forwards cancellation", async () => {
    const pdf = new Blob(["synthetic pdf"], { type: "application/pdf" });
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
        new Response(pdf, {
            headers: { "content-type": "application/pdf" },
        }),
    );
    const controller = new AbortController();

    const result = await createDocumentApi(fetcher).getSourceDocument(
        acceptedDocument.document_id,
        "operator-token",
        controller.signal,
    );

    expect(result).toEqual(pdf);
    expect(fetcher).toHaveBeenCalledWith(
        `/api/v1/documents/${acceptedDocument.document_id}/source`,
        {
            headers: { Authorization: "Bearer operator-token" },
            signal: controller.signal,
        },
    );
});

test("resolves a review with the configured bearer token", async () => {
    const resolution = {
        processing_run_id: acceptedDocument.processing_run_id,
        decision: "APPROVE",
        reviewer_id: "operator-42",
        resolved_at: "2026-09-17T18:00:00Z",
        replayed: false,
    } as const;
    const fetcher = vi
        .fn<typeof fetch>()
        .mockResolvedValue(jsonResponse(resolution));

    const result = await createDocumentApi(fetcher).resolveReview(
        acceptedDocument.document_id,
        {
            decision: "APPROVE",
            review_note: "Matched the supplier statement.",
            corrections: [],
        },
        "operator-token",
    );

    expect(result).toEqual(resolution);
    expect(fetcher).toHaveBeenCalledWith(
        `/api/v1/documents/${acceptedDocument.document_id}/review-resolution`,
        {
            method: "POST",
            headers: {
                Authorization: "Bearer operator-token",
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                decision: "APPROVE",
                review_note: "Matched the supplier statement.",
                corrections: [],
            }),
        },
    );
});

test("requests reprocessing with a bearer token and idempotency key", async () => {
    const reprocessing = {
        operation_id: "33333333-3333-4333-8333-333333333333",
        document_id: acceptedDocument.document_id,
        source_run_id: acceptedDocument.processing_run_id,
        replacement_run_id: "44444444-4444-4444-8444-444444444444",
        requested_at: "2026-09-20T10:15:00Z",
        replayed: false,
    } as const;
    const fetcher = vi
        .fn<typeof fetch>()
        .mockResolvedValue(jsonResponse(reprocessing, 202));

    const result = await createDocumentApi(fetcher).requestReprocessing(
        acceptedDocument.document_id,
        { reason: "Retry after the upstream OCR outage was resolved." },
        "operator-token",
        "reprocess-42",
    );

    expect(result).toEqual(reprocessing);
    expect(fetcher).toHaveBeenCalledWith(
        `/api/v1/documents/${acceptedDocument.document_id}/reprocessing-requests`,
        {
            method: "POST",
            headers: {
                Authorization: "Bearer operator-token",
                "Content-Type": "application/json",
                "Idempotency-Key": "reprocess-42",
            },
            body: JSON.stringify({
                reason: "Retry after the upstream OCR outage was resolved.",
            }),
        },
    );
});

test("maps RFC 9457 responses to a typed API error", async () => {
    const problem = {
        type: "urn:problem:document-not-found",
        title: "Document not found",
        status: 404,
        detail: `document not found: ${acceptedDocument.document_id}`,
    };
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
        jsonResponse(problem, 404, {
            "content-type": "application/problem+json",
        }),
    );

    await expect(
        createDocumentApi(fetcher).getStatus(
            acceptedDocument.document_id,
            operatorToken,
        ),
    ).rejects.toEqual(new DocumentApiProblem(problem));
});

test("does not trust malformed error payloads", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
        jsonResponse({ detail: "incomplete" }, 500, {
            "content-type": "application/problem+json",
        }),
    );

    await expect(
        createDocumentApi(fetcher).getStatus(
            acceptedDocument.document_id,
            operatorToken,
        ),
    ).rejects.toThrow("Document API request failed with status 500");
});

test.each([
    [401, "text/html", "<html>Unauthorized</html>"],
    [503, "application/problem+json", "not valid JSON"],
])(
    "preserves HTTP %s when a source error has no usable problem details",
    async (status, contentType, body) => {
        const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
            new Response(body, {
                status,
                headers: { "content-type": contentType },
            }),
        );
        await expect(
            createDocumentApi(fetcher).getSourceDocument(
                acceptedDocument.document_id,
                "synthetic-token",
            ),
        ).rejects.toEqual(new DocumentApiHttpError(status));
    },
);

function jsonResponse(
    body: unknown,
    status = 200,
    headers: HeadersInit = { "content-type": "application/json" },
): Response {
    return new Response(JSON.stringify(body), { status, headers });
}
