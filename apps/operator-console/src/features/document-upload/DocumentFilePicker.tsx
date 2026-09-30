import { FileText, X } from "lucide-react";
import { useRef, useState } from "react";

import { FeedbackMessage } from "../../components/ui/FeedbackMessage";

const MAX_FILE_BYTES = 20 * 1024 * 1024;

type DocumentFilePickerProps = {
    disabled?: boolean;
    onSelectionChange: (file: File | null) => void;
    selectedFile: File | null;
};

export function DocumentFilePicker({
    disabled = false,
    onSelectionChange,
    selectedFile,
}: DocumentFilePickerProps) {
    const inputRef = useRef<HTMLInputElement>(null);
    const [error, setError] = useState<string | null>(null);

    function selectFile(file: File | undefined) {
        if (file === undefined) {
            return;
        }
        if (file.type !== "application/pdf") {
            onSelectionChange(null);
            setError("Select a PDF document.");
            return;
        }
        if (file.size > MAX_FILE_BYTES) {
            onSelectionChange(null);
            setError("The document must not exceed 20 MiB.");
            return;
        }
        onSelectionChange(file);
        setError(null);
    }

    function clearSelection() {
        onSelectionChange(null);
        setError(null);
        if (inputRef.current !== null) {
            inputRef.current.value = "";
        }
    }

    return (
        <div>
            <div className="flex min-w-0 items-center gap-2">
                <label
                    htmlFor="document-file"
                    className={`flex min-h-18 min-w-0 flex-1 items-center gap-3 rounded border border-dashed border-app-border-strong bg-app-surface px-4 py-3 transition-colors focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-app-focus ${disabled ? "cursor-default opacity-60" : "cursor-pointer hover:border-app-accent"}`}
                >
                    <FileText
                        aria-hidden="true"
                        className="shrink-0 text-app-accent"
                        size={24}
                        strokeWidth={1.6}
                    />
                    <span className="min-w-0">
                        <span className="block truncate text-sm font-semibold">
                            {selectedFile?.name ?? "Choose a PDF"}
                        </span>
                        <span className="mt-1 block text-xs text-app-muted">
                            {selectedFile === null
                                ? "PDF / Up to 20 MiB / Up to 50 pages"
                                : formatBytes(selectedFile.size)}
                        </span>
                    </span>
                    <input
                        ref={inputRef}
                        id="document-file"
                        type="file"
                        accept="application/pdf,.pdf"
                        aria-label="Choose a PDF"
                        disabled={disabled}
                        className="sr-only"
                        onChange={(event) =>
                            selectFile(event.target.files?.[0])
                        }
                    />
                </label>
                {selectedFile !== null ? (
                    <button
                        type="button"
                        onClick={clearSelection}
                        disabled={disabled}
                        className="grid size-11 shrink-0 place-items-center rounded text-app-muted hover:bg-app-canvas hover:text-app-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus"
                        aria-label="Remove selected document"
                        title="Remove selected document"
                    >
                        <X aria-hidden="true" size={18} />
                    </button>
                ) : null}
            </div>
            {error !== null ? (
                <FeedbackMessage className="mt-3" role="alert" tone="danger">
                    {error}
                </FeedbackMessage>
            ) : null}
        </div>
    );
}

function formatBytes(bytes: number): string {
    if (bytes < 1024) {
        return `${bytes} B`;
    }
    return `${(bytes / 1024).toFixed(1)} KiB`;
}
