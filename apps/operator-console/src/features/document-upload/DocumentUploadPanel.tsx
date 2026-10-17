import { useMutation } from "@tanstack/react-query";
import { CheckCircle2, LoaderCircle, Upload } from "lucide-react";
import { type FormEvent, useState } from "react";

import {
    createDocumentApi,
    type AcceptedDocument,
    type DocumentApi,
    DocumentApiProblem,
} from "../../api/documentApi";
import { Button } from "../../components/ui/Button";
import { FeedbackMessage } from "../../components/ui/FeedbackMessage";
import { DocumentFilePicker } from "./DocumentFilePicker";
import { useOperatorToken } from "../operator-access/operatorToken";

type UploadApi = Pick<DocumentApi, "upload">;

type DocumentUploadPanelProps = {
    api?: UploadApi;
    idGenerator?: () => string;
    onAccepted?: (document: AcceptedDocument) => void;
};

const defaultApi = createDocumentApi();

export function DocumentUploadPanel({
    api = defaultApi,
    idGenerator = () => crypto.randomUUID(),
    onAccepted,
}: DocumentUploadPanelProps) {
    const { operatorToken } = useOperatorToken();
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [idempotencyKey, setIdempotencyKey] = useState<string | null>(null);
    const upload = useMutation({
        mutationFn: ({ file, key }: { file: File; key: string }) =>
            api.upload(file, key, operatorToken),
        onSuccess: onAccepted,
    });

    function changeSelection(file: File | null) {
        setSelectedFile(file);
        setIdempotencyKey(file === null ? null : idGenerator());
        upload.reset();
    }

    function submit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (selectedFile !== null && idempotencyKey !== null) {
            upload.mutate({ file: selectedFile, key: idempotencyKey });
        }
    }

    const failureMessage =
        upload.error instanceof DocumentApiProblem
            ? upload.error.problem.detail
            : "The document could not be uploaded. Try again.";

    return (
        <form onSubmit={submit}>
            <div className="flex flex-col items-stretch gap-3 sm:flex-row sm:items-start">
                <div className="min-w-0 flex-1">
                    <DocumentFilePicker
                        disabled={upload.isPending}
                        selectedFile={selectedFile}
                        onSelectionChange={changeSelection}
                    />
                </div>
                <Button
                    className="shrink-0 sm:mt-3"
                    type="submit"
                    disabled={
                        selectedFile === null ||
                        upload.isPending ||
                        upload.isSuccess
                    }
                    size="lg"
                    variant="primary"
                >
                    {upload.isPending ? (
                        <LoaderCircle
                            aria-hidden="true"
                            className="motion-safe:animate-spin"
                            size={18}
                        />
                    ) : (
                        <Upload aria-hidden="true" size={18} />
                    )}
                    {upload.isPending ? "Uploading" : "Upload document"}
                </Button>
            </div>

            <div>
                {upload.isError ? (
                    <FeedbackMessage
                        className="mt-5"
                        focusOnMount
                        role="alert"
                        tone="danger"
                    >
                        {failureMessage}
                    </FeedbackMessage>
                ) : null}

                {upload.data !== undefined ? (
                    <section className="mt-6 border border-app-success-border bg-app-success-surface p-5">
                        <div className="flex items-center gap-2 text-app-success">
                            <CheckCircle2 aria-hidden="true" size={20} />
                            <h2 className="font-semibold">
                                {upload.data.replayed
                                    ? "Previously accepted"
                                    : "Document accepted"}
                            </h2>
                        </div>
                        <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
                            <Identifier
                                label="Document ID"
                                value={upload.data.document_id}
                            />
                            <Identifier
                                label="Processing run ID"
                                value={upload.data.processing_run_id}
                            />
                        </dl>
                    </section>
                ) : null}
            </div>
        </form>
    );
}

function Identifier({ label, value }: { label: string; value: string }) {
    return (
        <div className="min-w-0">
            <dt className="text-xs font-medium text-app-muted">{label}</dt>
            <dd className="mt-1 break-all font-mono text-xs">{value}</dd>
        </div>
    );
}
