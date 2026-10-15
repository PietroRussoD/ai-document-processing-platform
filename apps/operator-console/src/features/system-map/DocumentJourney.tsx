import { ExternalLink } from "lucide-react";
import { useState } from "react";

import { journeys, type JourneyId } from "./documentJourneyContent";

const repositoryUrl =
    "https://github.com/PietroRussoD/ai-document-processing-platform/blob/main";

export function DocumentJourney() {
    const [journeyId, setJourneyId] = useState<JourneyId>("auto-approval");
    const [selectedStep, setSelectedStep] = useState(0);
    const journey = journeys.find((item) => item.id === journeyId)!;
    const step = journey.steps[selectedStep];

    function selectJourney(id: JourneyId) {
        setJourneyId(id);
        setSelectedStep(0);
    }

    return (
        <section
            aria-labelledby="document-journey-heading"
            className="mt-12 border-t border-app-border pt-8"
        >
            <p className="text-xs font-semibold uppercase text-app-accent">
                Document lifecycle
            </p>
            <h2
                id="document-journey-heading"
                className="mt-1 text-xl font-semibold"
            >
                How a document moves
            </h2>
            <p className="mt-2 max-w-3xl text-sm text-app-muted">
                Choose an outcome to follow each step, its owner and the saved
                state changes. These are reference flows, not live traces.
            </p>

            <div
                role="group"
                aria-label="Processing outcome"
                className="mt-6 flex flex-wrap gap-2"
            >
                {journeys.map((item) => (
                    <button
                        key={item.id}
                        type="button"
                        aria-controls="journey-steps journey-step-details"
                        aria-pressed={item.id === journeyId}
                        className={`min-h-10 rounded border px-3 py-2 text-sm font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus ${item.id === journeyId ? "border-app-accent bg-emerald-50 text-app-accent" : "border-app-border bg-app-surface text-app-muted hover:border-app-border-strong"}`}
                        onClick={() => selectJourney(item.id)}
                    >
                        {item.label}
                    </button>
                ))}
            </div>

            <p role="status" aria-atomic="true" className="sr-only">
                {journey.label}. Step {selectedStep + 1} of{" "}
                {journey.steps.length} selected. {step.title}.
            </p>
            <p className="mt-5 text-sm text-app-muted">{journey.outcome}</p>
            <div className="mt-5 grid gap-7 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,0.8fr)]">
                <ol
                    id="journey-steps"
                    className="border-l-2 border-app-border pl-4"
                >
                    {journey.steps.map((item, index) => (
                        <li
                            key={`${journey.id}-${item.title}`}
                            className="relative pb-2 last:pb-0"
                        >
                            <button
                                type="button"
                                aria-controls="journey-step-details"
                                aria-pressed={index === selectedStep}
                                className={`w-full rounded border px-3 py-3 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus ${index === selectedStep ? "border-app-accent bg-emerald-50" : "border-transparent hover:border-app-border hover:bg-app-surface"}`}
                                onClick={() => setSelectedStep(index)}
                            >
                                <span className="block text-xs font-semibold text-app-accent">
                                    {String(index + 1).padStart(2, "0")} ·{" "}
                                    {item.owner}
                                </span>
                                <span className="mt-1 block text-sm font-semibold">
                                    {item.title}
                                </span>
                                <span className="mt-1 block text-xs text-app-muted">
                                    {item.state}
                                </span>
                            </button>
                            {index === selectedStep ? (
                                <a
                                    href="#journey-step-details-heading"
                                    className="inline-flex min-h-10 items-center text-sm font-semibold text-app-accent underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus"
                                >
                                    Go to step details
                                </a>
                            ) : null}
                        </li>
                    ))}
                </ol>

                <div
                    id="journey-step-details"
                    role="region"
                    aria-labelledby="journey-step-details-heading"
                    className="self-start border-y border-app-border bg-app-surface px-4 py-5 sm:px-6"
                >
                    <p className="text-xs font-semibold uppercase text-app-accent">
                        Selected step
                    </p>
                    <h3
                        id="journey-step-details-heading"
                        tabIndex={-1}
                        className="mt-1 text-lg font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus"
                    >
                        {step.title}
                    </h3>
                    <p className="mt-3 text-sm leading-6 text-app-muted">
                        {step.description}
                    </p>
                    <p className="mt-4 text-sm font-semibold">{step.state}</p>
                    <a
                        className="mt-4 inline-flex min-h-10 items-center gap-2 text-sm font-semibold text-app-accent underline underline-offset-4 hover:text-app-accent-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus"
                        href={`${repositoryUrl}/${step.referencePath}`}
                        rel="noreferrer"
                        target="_blank"
                    >
                        View implementation
                        <ExternalLink aria-hidden="true" size={16} />
                    </a>
                </div>
            </div>
        </section>
    );
}
