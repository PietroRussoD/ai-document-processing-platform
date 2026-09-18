import { CheckCircle2, CircleAlert, Info, type LucideIcon } from "lucide-react";
import { type ReactNode, useEffect, useRef } from "react";

type FeedbackTone = "danger" | "info" | "success" | "warning";

type FeedbackMessageProps = {
    children: ReactNode;
    className?: string;
    focusOnMount?: boolean;
    id?: string;
    role?: "alert" | "status";
    tone: FeedbackTone;
};

type TonePresentation = {
    icon: LucideIcon;
    className: string;
};

const presentations: Record<FeedbackTone, TonePresentation> = {
    danger: {
        icon: CircleAlert,
        className: "border-red-200 bg-red-50 text-app-danger",
    },
    info: {
        icon: Info,
        className: "border-blue-200 bg-blue-50 text-blue-900",
    },
    success: {
        icon: CheckCircle2,
        className:
            "border-app-success-border bg-app-success-surface text-app-success",
    },
    warning: {
        icon: CircleAlert,
        className: "border-amber-300 bg-amber-50 text-amber-900",
    },
};

export function FeedbackMessage({
    children,
    className = "",
    focusOnMount = false,
    id,
    role = "status",
    tone,
}: FeedbackMessageProps) {
    const messageRef = useRef<HTMLDivElement>(null);
    const presentation = presentations[tone];
    const Icon = presentation.icon;

    useEffect(() => {
        if (focusOnMount) {
            messageRef.current?.focus();
        }
    }, [focusOnMount]);

    return (
        <div
            ref={messageRef}
            id={id}
            role={role}
            tabIndex={focusOnMount ? -1 : undefined}
            className={`flex items-start gap-2 border-l-2 px-3 py-2 text-sm ${presentation.className} ${className}`}
        >
            <Icon aria-hidden="true" className="mt-0.5 shrink-0" size={18} />
            <div className="min-w-0">{children}</div>
        </div>
    );
}
