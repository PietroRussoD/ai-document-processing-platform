import { FileText, X } from "lucide-react";
import { useRef, useState } from "react";

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
        <div className="border border-app-border bg-app-surface p-5 sm:p-7">
            <label
                htmlFor="document-file"
                className="flex min-h-44 cursor-pointer flex-col items-center justify-center border border-dashed border-app-border-strong bg-app-canvas px-5 py-8 text-center transition-colors hover:border-app-accent focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-app-focus"
            >
                <FileText
                    aria-hidden="true"
                    className="mb-4 text-app-accent"
                    size={28}
                    strokeWidth={1.6}
                />
                <span className="font-semibold">Choose a PDF</span>
                <span className="mt-1 text-sm text-app-muted">
                    The document stays local until submitted.
                </span>
                <input
                    ref={inputRef}
                    id="document-file"
                    type="file"
                    accept="application/pdf,.pdf"
                    aria-label="Choose a PDF"
                    disabled={disabled}
                    className="sr-only"
                    onChange={(event) => selectFile(event.target.files?.[0])}
                />
            </label>

            {error !== null ? (
                <p
                    role="alert"
                    className="mt-4 border-l-2 border-app-danger pl-3 text-sm text-app-danger"
                >
                    {error}
                </p>
            ) : null}

            {selectedFile !== null ? (
                <div className="mt-4 flex min-w-0 items-center gap-3 border-t border-app-border pt-4">
                    <FileText
                        aria-hidden="true"
                        className="shrink-0 text-app-accent"
                        size={20}
                    />
                    <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium">
                            {selectedFile.name}
                        </p>
                        <p className="text-xs text-app-muted">
                            {formatBytes(selectedFile.size)}
                        </p>
                    </div>
                    <button
                        type="button"
                        onClick={clearSelection}
                        disabled={disabled}
                        className="grid size-9 shrink-0 place-items-center rounded text-app-muted hover:bg-app-canvas hover:text-app-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus"
                        aria-label="Remove selected document"
                        title="Remove selected document"
                    >
                        <X aria-hidden="true" size={18} />
                    </button>
                </div>
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
