import { FileText } from "lucide-react";

import { DocumentsPage } from "../features/documents/DocumentsPage";
import { SystemMapPage } from "../features/system-map/SystemMapPage";

export function App() {
    const isSystemMap = window.location.pathname === "/system-map";

    return (
        <div className="min-h-screen bg-app-canvas text-app-foreground">
            <a
                href="#main-content"
                className="fixed left-3 top-3 z-50 -translate-y-20 rounded bg-app-foreground px-3 py-2 text-sm font-semibold text-white transition-transform focus:translate-y-0"
            >
                Skip to main content
            </a>
            <header className="border-b border-app-border bg-app-surface">
                <div className="mx-auto flex min-h-16 max-w-6xl flex-wrap items-center gap-3 px-4 py-3 sm:px-6">
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
                    <nav
                        aria-label="Console views"
                        className="ml-auto flex gap-4 text-sm"
                    >
                        <a
                            aria-current={isSystemMap ? undefined : "page"}
                            className={`font-semibold hover:text-app-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus ${isSystemMap ? "text-app-muted" : "text-app-accent"}`}
                            href="/"
                        >
                            Documents
                        </a>
                        <a
                            aria-current={isSystemMap ? "page" : undefined}
                            className={`font-semibold hover:text-app-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus ${isSystemMap ? "text-app-accent" : "text-app-muted"}`}
                            href="/system-map"
                        >
                            System Map
                        </a>
                    </nav>
                </div>
            </header>

            <main
                id="main-content"
                className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 sm:py-12"
            >
                {isSystemMap ? <SystemMapPage /> : <DocumentsPage />}
            </main>
        </div>
    );
}
