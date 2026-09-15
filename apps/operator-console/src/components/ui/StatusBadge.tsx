type StatusBadgeProps = {
    label: string;
    tone: "danger" | "info" | "neutral" | "success" | "warning";
};

const toneClasses: Record<StatusBadgeProps["tone"], string> = {
    danger: "border-red-200 bg-red-50 text-red-800",
    info: "border-blue-200 bg-blue-50 text-blue-800",
    neutral: "border-zinc-200 bg-zinc-50 text-zinc-700",
    success: "border-green-200 bg-green-50 text-green-800",
    warning: "border-amber-200 bg-amber-50 text-amber-900",
};

export function StatusBadge({ label, tone }: StatusBadgeProps) {
    return (
        <span
            className={`inline-flex min-h-7 items-center rounded border px-2.5 py-1 text-xs font-semibold ${toneClasses[tone]}`}
        >
            {label}
        </span>
    );
}
