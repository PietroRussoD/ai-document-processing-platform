import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import {
    type AcceptedDocument,
    createDocumentApi,
    type DocumentApi,
} from "../../api/documentApi";
import { DocumentStatusPanel } from "../document-status/DocumentStatusPanel";
import { ReviewDraftProvider } from "../document-review/ReviewDraftProvider";
import { DocumentUploadPanel } from "../document-upload/DocumentUploadPanel";
import { DocumentWorkQueuesPanel } from "../document-work-queues/DocumentWorkQueuesPanel";

type DocumentsApi = Pick<DocumentApi, "upload" | "getStatus" | "listWorkQueue">;

const defaultApi = createDocumentApi();

export function DocumentsPage({ api = defaultApi }: { api?: DocumentsApi }) {
    return (
        <ReviewDraftProvider>
            <DocumentsWorkspace api={api} />
        </ReviewDraftProvider>
    );
}

function DocumentsWorkspace({ api }: { api: DocumentsApi }) {
    const queryClient = useQueryClient();
    const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(
        selectedDocumentFromUrl,
    );

    useEffect(() => {
        function syncSelection() {
            setSelectedDocumentId(selectedDocumentFromUrl());
        }
        window.addEventListener("popstate", syncSelection);
        return () => window.removeEventListener("popstate", syncSelection);
    }, []);

    function selectDocument(documentId: string | null) {
        const url = new URL(window.location.href);
        if (url.searchParams.get("documentId") !== documentId) {
            if (documentId === null) {
                url.searchParams.delete("documentId");
            } else {
                url.searchParams.set("documentId", documentId);
            }
            window.history.pushState(
                {},
                "",
                `${url.pathname}${url.search}${url.hash}`,
            );
        }
        setSelectedDocumentId(documentId);
    }

    function acceptDocument(document: AcceptedDocument) {
        selectDocument(document.document_id);
        void queryClient.invalidateQueries({
            queryKey: ["document-work-queue"],
        });
    }

    return (
        <>
            <section aria-labelledby="intake-heading">
                <div className="mb-4">
                    <h1 id="intake-heading" className="text-xl font-semibold">
                        Upload a document
                    </h1>
                </div>
                <DocumentUploadPanel api={api} onAccepted={acceptDocument} />
            </section>
            <DocumentWorkQueuesPanel
                api={api}
                detailsId="selected-document-details"
                selectedDocumentId={selectedDocumentId}
                onSelectDocument={selectDocument}
            />
            <div id="selected-document-details" className="mt-4">
                {selectedDocumentId !== null ? (
                    <p className="text-sm text-app-muted">
                        Unsaved review drafts are kept while you switch
                        documents. Save your review before leaving or reloading
                        this page.
                    </p>
                ) : null}
                {selectedDocumentId !== null ? (
                    <DocumentStatusPanel
                        key={selectedDocumentId}
                        api={api}
                        documentId={selectedDocumentId}
                    />
                ) : null}
            </div>
        </>
    );
}

function selectedDocumentFromUrl(): string | null {
    return new URL(window.location.href).searchParams.get("documentId");
}
