import {
    BarChart3,
    Cog,
    Database,
    ExternalLink,
    FileText,
    HardDrive,
    ScanText,
    Send,
    Server,
    Workflow,
    type LucideIcon,
} from "lucide-react";
import { useState } from "react";

import {
    processingPath,
    supportingNodes,
    systemNodes,
    type SystemNodeId,
} from "./systemMapContent";

const repositoryUrl =
    "https://github.com/PietroRussoD/ai-document-processing-platform/blob/main";

const icons: Record<SystemNodeId, LucideIcon> = {
    console: FileText,
    api: Server,
    postgres: Database,
    dispatcher: Send,
    temporal: Workflow,
    worker: Cog,
    blob: HardDrive,
    extractors: ScanText,
    observability: BarChart3,
};

export function SystemMapPage() {
    const [selectedId, setSelectedId] = useState<SystemNodeId>("console");
    const selectedNode = systemNodes[selectedId];

    return (
        <section aria-labelledby="system-map-heading">
            <div className="border-b border-app-border pb-6">
                <p className="text-xs font-semibold uppercase text-app-accent">
                    Architecture
                </p>
                <h1
                    id="system-map-heading"
                    className="mt-2 text-2xl font-semibold sm:text-3xl"
                >
                    System Map
                </h1>
                <p className="mt-2 max-w-3xl text-sm text-app-muted">
                    Implemented local topology. This reference map does not
                    report live health or trace individual requests.
                </p>
            </div>

            <section aria-labelledby="processing-path-heading" className="pt-7">
                <h2
                    id="processing-path-heading"
                    className="text-lg font-semibold"
                >
                    Processing path
                </h2>
                <ol className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {processingPath.map((id, index) => (
                        <li key={id} className="min-w-0">
                            <SystemNodeButton
                                id={id}
                                index={index + 1}
                                onSelect={setSelectedId}
                                selected={selectedId === id}
                            />
                        </li>
                    ))}
                </ol>
            </section>

            <section aria-labelledby="supporting-heading" className="mt-8">
                <h2 id="supporting-heading" className="text-lg font-semibold">
                    Supporting components
                </h2>
                <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {supportingNodes.map((id) => (
                        <SystemNodeButton
                            key={id}
                            id={id}
                            onSelect={setSelectedId}
                            selected={selectedId === id}
                        />
                    ))}
                </div>
            </section>

            <section
                id="system-node-details"
                aria-labelledby="system-node-details-heading"
                aria-live="polite"
                className="mt-8 border-y border-app-border bg-app-surface px-4 py-5 sm:px-6"
            >
                <p className="text-xs font-semibold uppercase text-app-accent">
                    Component detail
                </p>
                <h2
                    id="system-node-details-heading"
                    className="mt-1 text-lg font-semibold"
                >
                    {selectedNode.title}
                </h2>
                <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-2">
                    <div>
                        <dt className="font-semibold">Receives</dt>
                        <dd className="mt-1 text-app-muted">
                            {selectedNode.receives}
                        </dd>
                    </div>
                    <div>
                        <dt className="font-semibold">Produces</dt>
                        <dd className="mt-1 text-app-muted">
                            {selectedNode.produces}
                        </dd>
                    </div>
                </dl>
                <a
                    className="mt-5 inline-flex min-h-10 items-center gap-2 text-sm font-semibold text-app-accent underline underline-offset-4 hover:text-app-accent-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus"
                    href={`${repositoryUrl}/${selectedNode.referencePath}`}
                    rel="noreferrer"
                    target="_blank"
                >
                    View source
                    <ExternalLink aria-hidden="true" size={16} />
                </a>
            </section>
        </section>
    );
}

function SystemNodeButton({
    id,
    index,
    onSelect,
    selected,
}: {
    id: SystemNodeId;
    index?: number;
    onSelect: (id: SystemNodeId) => void;
    selected: boolean;
}) {
    const node = systemNodes[id];
    const Icon = icons[id];

    return (
        <button
            type="button"
            aria-controls="system-node-details"
            aria-pressed={selected}
            className={`flex min-h-32 w-full min-w-0 flex-col rounded-md border p-4 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus ${selected ? "border-app-accent bg-emerald-50" : "border-app-border bg-app-surface hover:border-app-border-strong"}`}
            onClick={() => onSelect(id)}
        >
            <span className="flex w-full items-center gap-2 text-app-accent">
                <Icon aria-hidden="true" size={18} />
                {index === undefined ? null : (
                    <span className="ml-auto text-xs font-semibold">
                        {String(index).padStart(2, "0")}
                    </span>
                )}
            </span>
            <span className="mt-3 text-sm font-semibold text-app-foreground">
                {node.title}
            </span>
            <span className="mt-1 text-xs leading-5 text-app-muted">
                {node.summary}
            </span>
            {node.optional ? (
                <span className="mt-2 text-xs font-medium text-app-muted">
                    Optional
                </span>
            ) : null}
        </button>
    );
}
