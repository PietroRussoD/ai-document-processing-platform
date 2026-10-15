import { useEffect, useMemo, useState, type PropsWithChildren } from "react";

import {
    hasUnsavedReviewDraft,
    ReviewDraftContext,
    type ReviewDrafts,
} from "./reviewDraft";

export function ReviewDraftProvider({ children }: PropsWithChildren) {
    const [drafts, setDrafts] = useState<ReviewDrafts>({});
    const value = useMemo(() => ({ drafts, setDrafts }), [drafts]);
    const hasUnsavedChanges = Object.values(drafts).some(
        (draft) => draft !== undefined && hasUnsavedReviewDraft(draft),
    );

    useEffect(() => {
        if (!hasUnsavedChanges) {
            return;
        }
        function warnBeforeLeaving(event: BeforeUnloadEvent) {
            event.preventDefault();
            event.returnValue = true;
        }
        window.addEventListener("beforeunload", warnBeforeLeaving);
        return () =>
            window.removeEventListener("beforeunload", warnBeforeLeaving);
    }, [hasUnsavedChanges]);

    return (
        <ReviewDraftContext.Provider value={value}>
            {children}
        </ReviewDraftContext.Provider>
    );
}
