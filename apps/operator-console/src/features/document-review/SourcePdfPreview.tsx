import { useEffect, useRef, useState } from "react";

import { type DocumentApi } from "../../api/documentApi";
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
        } catch {
            if (!controller.signal.aborted) {
                setErrorMessage("The source PDF could not be loaded.");
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
            className="mt-5 border-t border-amber-200 pt-5"
        >
            <h4 className="text-sm font-semibold text-amber-950">
                Original source document
            </h4>
            <p className="mt-1 text-sm text-amber-900">
                Inspect the original PDF before deciding whether to correct or
                approve extracted values.
            </p>
            <div className="mt-3">
                {sourceUrl === null ? (
                    <Button
                        aria-controls="source-pdf-preview"
                        aria-expanded={false}
                        disabled={!operatorToken || isLoading}
                        onClick={() => void openPreview()}
                        variant="secondary"
                    >
                        {isLoading ? "Loading source PDF" : "View source PDF"}
                    </Button>
                ) : (
                    <Button
                        aria-controls="source-pdf-preview"
                        aria-expanded={true}
                        onClick={closePreview}
                        variant="secondary"
                    >
                        Close source PDF
                    </Button>
                )}
            </div>
            {isLoading ? (
                <FeedbackMessage className="mt-3" role="status" tone="info">
                    Loading source PDF
                </FeedbackMessage>
            ) : null}
            {errorMessage !== null ? (
                <FeedbackMessage className="mt-3" role="alert" tone="danger">
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
