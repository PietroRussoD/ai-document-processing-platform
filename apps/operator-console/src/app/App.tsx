import { FileText } from "lucide-react";

import { DocumentFilePicker } from "../features/document-upload/DocumentFilePicker";

export function App() {
    return (
        <div className="min-h-screen bg-app-canvas text-app-foreground">
            <a
                href="#main-content"
                className="fixed left-3 top-3 z-50 -translate-y-20 rounded bg-app-foreground px-3 py-2 text-sm font-semibold text-white transition-transform focus:translate-y-0"
            >
                Skip to main content
            </a>
            <header className="border-b border-app-border bg-app-surface">
                <div className="mx-auto flex h-16 max-w-6xl items-center gap-3 px-4 sm:px-6">
                    <span className="grid size-9 place-items-center rounded bg-app-foreground text-white">
                        <FileText
                            aria-hidden="true"
                            size={19}
                            strokeWidth={1.8}
                        />
                    </span>
                    <div>
                        <p className="text-sm font-semibold">
                            Document Processing
                        </p>
                        <p className="text-xs text-app-muted">
                            Operator console
                        </p>
                    </div>
                </div>
            </header>

            <main
                id="main-content"
                className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 sm:py-12"
            >
                <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_18rem]">
                    <section aria-labelledby="intake-heading">
                        <div className="mb-6">
                            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-app-accent">
                                Document intake
                            </p>
                            <h1
                                id="intake-heading"
                                className="text-3xl font-semibold sm:text-4xl"
                            >
                                Upload a business document
                            </h1>
                        </div>
                        <DocumentFilePicker />
                    </section>

                    <aside
                        className="border-l-2 border-app-border pl-5"
                        aria-labelledby="requirements-heading"
                    >
                        <h2
                            id="requirements-heading"
                            className="text-sm font-semibold"
                        >
                            File requirements
                        </h2>
                        <ul className="mt-3 space-y-2 text-sm text-app-muted">
                            <li>PDF format</li>
                            <li>Up to 20 MiB</li>
                            <li>Up to 50 pages</li>
                        </ul>
                    </aside>
                </div>
            </main>
        </div>
    );
}
