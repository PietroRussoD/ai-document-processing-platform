import { ExternalLink, FileText, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import {
    type DocumentApi,
    DocumentApiHttpError,
    DocumentApiProblem,
} from "../../api/documentApi";
import { Button } from "../../components/ui/Button";
import { FeedbackMessage } from "../../components/ui/FeedbackMessage";

type SourceDocumentApi = Pick<DocumentApi, "getSourceDocument">;

type SourcePdfPreviewProps = {
    api: SourceDocumentApi;
    documentId: string;
    operatorToken: string;
};

export function SourcePdfPreview({
    api,
    documentId,
    operatorToken,
}: SourcePdfPreviewProps) {
    const [sourceUrl, setSourceUrl] = useState<string | null>(null);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const objectUrl = useRef<string | null>(null);
    const requestController = useRef<AbortController | null>(null);

    useEffect(
        () => () => {
            requestController.current?.abort();
            if (objectUrl.current !== null) {
                URL.revokeObjectURL(objectUrl.current);
            }
        },
        [],
    );

    async function openPreview() {
        setIsLoading(true);
        setErrorMessage(null);
        const controller = new AbortController();
        requestController.current = controller;

        try {
            const pdf = await api.getSourceDocument(
                documentId,
                operatorToken,
                controller.signal,
            );
            if (!controller.signal.aborted) {
                const nextUrl = URL.createObjectURL(pdf);
                objectUrl.current = nextUrl;
                setSourceUrl(nextUrl);
            }
        } catch (error) {
            if (!controller.signal.aborted) {
                setErrorMessage(sourceFailureMessage(error));
            }
        } finally {
            if (!controller.signal.aborted) {
                setIsLoading(false);
            }
        }
    }

    function closePreview() {
        requestController.current?.abort();
        if (objectUrl.current !== null) {
            URL.revokeObjectURL(objectUrl.current);
            objectUrl.current = null;
        }
        setSourceUrl(null);
        setErrorMessage(null);
    }

    return (
        <div
            aria-busy={isLoading}
            className="min-w-0 border-t border-amber-200 pt-5"
        >
            <h4 className="text-sm font-semibold text-amber-950">
                Original source document
            </h4>
            <div className="mt-3 flex flex-wrap items-center gap-3">
                {sourceUrl === null ? (
                    <Button
                        aria-controls="source-pdf-preview"
                        aria-expanded={false}
                        aria-describedby={
                            errorMessage ? "source-pdf-error" : undefined
                        }
                        disabled={!operatorToken || isLoading}
                        onClick={() => void openPreview()}
                        variant="secondary"
                    >
                        <FileText aria-hidden="true" size={17} />
                        {isLoading
                            ? "Loading source PDF"
                            : errorMessage
                              ? "Retry loading PDF"
                              : "View source PDF"}
                    </Button>
                ) : (
                    <Button
                        aria-controls="source-pdf-preview"
                        aria-expanded={true}
                        onClick={closePreview}
                        variant="secondary"
                    >
                        <X aria-hidden="true" size={17} />
                        Close source PDF
                    </Button>
                )}
                {sourceUrl !== null ? (
                    <a
                        className="inline-flex min-h-10 items-center gap-2 rounded px-2 text-sm font-medium text-app-accent underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus"
                        href={sourceUrl}
                        rel="noopener noreferrer"
                        target="_blank"
                    >
                        <ExternalLink aria-hidden="true" size={17} />
                        Open PDF in new tab
                    </a>
                ) : null}
            </div>
            {isLoading ? (
                <FeedbackMessage className="mt-3" role="status" tone="info">
                    Loading source PDF
                </FeedbackMessage>
            ) : null}
            {errorMessage !== null ? (
                <FeedbackMessage
                    id="source-pdf-error"
                    className="mt-3"
                    role="alert"
                    tone="danger"
                >
                    {errorMessage}
                </FeedbackMessage>
            ) : null}
            <div id="source-pdf-preview">
                {sourceUrl !== null ? (
                    <iframe
                        className="mt-4 h-[min(70vh,48rem)] w-full border border-amber-300 bg-white"
                        src={sourceUrl}
                        title="Source PDF preview"
                    />
                ) : null}
            </div>
        </div>
    );
}

function sourceFailureMessage(error: unknown): string {
    const status =
        error instanceof DocumentApiProblem
            ? error.problem.status
            : error instanceof DocumentApiHttpError
              ? error.status
              : null;
    if (status === 401) {
        return "The operator token was not accepted. Check the token above, then retry loading the PDF.";
    }
    if (status === 403) {
        return "Access to the source PDF was denied. Check your operator permissions before retrying.";
    }
    if (status === 404) {
        return "The source PDF is unavailable for this document.";
    }
    if (status !== null && status >= 500) {
        return "The server could not provide the source PDF. Try again later.";
    }
    if (error instanceof TypeError) {
        return "The source PDF could not be reached. Check your connection and try again.";
    }
    return "The source PDF could not be loaded. Try again.";
}
