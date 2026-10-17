import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import {
    type AcceptedDocument,
    createDocumentApi,
    type DocumentApi,
    DocumentApiHttpError,
    DocumentApiProblem,
} from "../../api/documentApi";
import { DocumentStatusPanel } from "../document-status/DocumentStatusPanel";
import { Button } from "../../components/ui/Button";
import { OperatorTokenProvider } from "../operator-access/OperatorTokenProvider";
import { OperatorAccessPanel } from "../operator-access/OperatorAccessPanel";
import { ReviewDraftProvider } from "../document-review/ReviewDraftProvider";
import { DocumentUploadPanel } from "../document-upload/DocumentUploadPanel";
import { DocumentWorkQueuesPanel } from "../document-work-queues/DocumentWorkQueuesPanel";
import { FeedbackMessage } from "../../components/ui/FeedbackMessage";
import { useOperatorToken } from "../operator-access/operatorToken";

type DocumentsApi = Pick<DocumentApi, "upload" | "getStatus" | "listWorkQueue">;

const defaultApi = createDocumentApi();

export function DocumentsPage({ api = defaultApi }: { api?: DocumentsApi }) {
    return (
        <OperatorTokenProvider>
            <ReviewDraftProvider>
                <DocumentsWorkspace api={api} />
            </ReviewDraftProvider>
        </OperatorTokenProvider>
    );
}

function DocumentsWorkspace({ api }: { api: DocumentsApi }) {
    const queryClient = useQueryClient();
    const { operatorToken, setOperatorToken, isConnected, setIsConnected } =
        useOperatorToken();
    const [isConnecting, setIsConnecting] = useState(false);
    const [connectionError, setConnectionError] = useState<string | null>(null);

    async function connect(token: string) {
        setIsConnecting(true);
        setConnectionError(null);
        setIsConnected(false);
        setOperatorToken("");
        removeDocumentQueries();
        try {
            const firstQueuePage = await api.listWorkQueue("ACTIVE", token, 0);
            setOperatorToken(token);
            setIsConnected(true);
            queryClient.setQueryData(
                ["document-work-queue", "ACTIVE", 0],
                firstQueuePage,
            );
        } catch (error) {
            setConnectionError(
                (error instanceof DocumentApiHttpError &&
                    error.status === 401) ||
                    (error instanceof DocumentApiProblem &&
                        error.problem.status === 401)
                    ? "The operator token was rejected. Check it and try again."
                    : "The token could not be checked. Check the connection and try again.",
            );
        } finally {
            setIsConnecting(false);
        }
    }

    function disconnect() {
        setIsConnected(false);
        setOperatorToken("");
        setConnectionError(null);
        removeDocumentQueries();
    }

    function removeDocumentQueries() {
        queryClient.removeQueries({
            predicate: ({ queryKey }) =>
                queryKey[0] === "document-work-queue" ||
                queryKey[0] === "document-status",
        });
    }

    return (
        <>
            <header className="mb-6">
                <h1 className="text-2xl font-semibold">Documents</h1>
                <p className="mt-2 text-sm text-app-muted">
                    Upload a PDF or choose a document from a work queue to
                    follow its processing and review it.
                </p>
            </header>
            <OperatorAccessPanel
                connectionError={connectionError}
                isConnecting={isConnecting}
                onConnect={connect}
                onDisconnect={disconnect}
            />
            {isConnected && operatorToken ? (
                <DocumentsContent api={api} />
            ) : (
                <FeedbackMessage className="mt-4" tone="info">
                    Document queues and details are available after token
                    verification.
                </FeedbackMessage>
            )}
        </>
    );
}

function DocumentsContent({ api }: { api: DocumentsApi }) {
    const queryClient = useQueryClient();
    const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(
        selectedDocumentFromUrl,
    );

    const uploadDisclosure = useRef<HTMLDetailsElement>(null);
    const queueDisclosure = useRef<HTMLDetailsElement>(null);
    const workspaceHeading = useRef<HTMLHeadingElement>(null);
    const queueSummary = useRef<HTMLElement>(null);
    const previousSelection = useRef(selectedDocumentId);

    useEffect(() => {
        if (uploadDisclosure.current)
            uploadDisclosure.current.open = selectedDocumentId === null;
        if (queueDisclosure.current)
            queueDisclosure.current.open = selectedDocumentId === null;
        if (selectedDocumentId !== null) {
            workspaceHeading.current?.focus();
        } else if (previousSelection.current !== null) {
            queueSummary.current?.focus();
        }
        previousSelection.current = selectedDocumentId;
    }, [selectedDocumentId]);

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
            <details
                ref={uploadDisclosure}
                open={selectedDocumentId === null}
                className="border-y border-app-border py-4"
            >
                <summary className="cursor-pointer text-base font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus">
                    <h2 id="intake-heading" className="inline">
                        Upload a document
                    </h2>
                </summary>
                <div className="mt-4">
                    <DocumentUploadPanel
                        api={api}
                        onAccepted={acceptDocument}
                    />
                </div>
            </details>
            <details
                ref={queueDisclosure}
                open={selectedDocumentId === null}
                className="mt-4 border-y border-app-border py-4"
            >
                <summary
                    ref={queueSummary}
                    className="cursor-pointer text-base font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus"
                >
                    Browse work queues
                </summary>
                <DocumentWorkQueuesPanel
                    api={api}
                    className="mt-5"
                    detailsId="selected-document-details"
                    selectedDocumentId={selectedDocumentId}
                    onSelectDocument={selectDocument}
                />
            </details>
            <div id="selected-document-details" className="mt-4">
                {selectedDocumentId !== null ? (
                    <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                        <h2
                            ref={workspaceHeading}
                            tabIndex={-1}
                            className="text-xl font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus"
                        >
                            Document workspace
                        </h2>
                        <Button onClick={() => selectDocument(null)} size="sm">
                            Back to work queues
                        </Button>
                    </div>
                ) : null}
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
