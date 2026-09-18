import { expect, test, vi } from "vitest";

import { createDocumentApi, DocumentApiProblem } from "./documentApi";

const acceptedDocument = {
    document_id: "11111111-1111-4111-8111-111111111111",
    processing_run_id: "22222222-2222-4222-8222-222222222222",
    accepted_at: "2026-09-14T19:00:00Z",
    replayed: false,
};

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
    );

    expect(result).toEqual(acceptedDocument);
    expect(fetcher).toHaveBeenCalledOnce();
    const [url, request] = fetcher.mock.calls[0];
    expect(url).toBe("/api/v1/documents");
    expect(request?.method).toBe("POST");
    expect(request?.headers).toEqual({ "Idempotency-Key": "upload-42" });
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
        controller.signal,
    );

    expect(result).toEqual(status);
    expect(fetcher).toHaveBeenCalledWith(
        `/api/v1/documents/${acceptedDocument.document_id}`,
        { signal: controller.signal },
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
        createDocumentApi(fetcher).getStatus(acceptedDocument.document_id),
    ).rejects.toEqual(new DocumentApiProblem(problem));
});

test("does not trust malformed error payloads", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
        jsonResponse({ detail: "incomplete" }, 500, {
            "content-type": "application/problem+json",
        }),
    );

    await expect(
        createDocumentApi(fetcher).getStatus(acceptedDocument.document_id),
    ).rejects.toThrow("Document API request failed with status 500");
});

function jsonResponse(
    body: unknown,
    status = 200,
    headers: HeadersInit = { "content-type": "application/json" },
): Response {
    return new Response(JSON.stringify(body), { status, headers });
}
