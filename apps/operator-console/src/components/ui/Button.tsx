import { type ComponentPropsWithoutRef } from "react";

type ButtonSize = "lg" | "md" | "sm";
type ButtonVariant = "danger" | "primary" | "secondary";

type ButtonProps = ComponentPropsWithoutRef<"button"> & {
    size?: ButtonSize;
    variant?: ButtonVariant;
};

const sizeClasses: Record<ButtonSize, string> = {
    lg: "h-11 px-5",
    md: "h-10 px-4",
    sm: "h-9 px-3",
};

const variantClasses: Record<ButtonVariant, string> = {
    danger: "border border-app-danger text-app-danger hover:bg-red-50 disabled:text-app-danger",
    primary:
        "bg-app-accent text-white hover:bg-app-accent-hover disabled:bg-app-accent",
    secondary:
        "border border-app-border-strong text-app-foreground hover:bg-app-canvas",
};

export function Button({
    className = "",
    size = "md",
    type = "button",
    variant = "secondary",
    ...props
}: ButtonProps) {
    return (
        <button
            type={type}
            className={`inline-flex items-center justify-center gap-2 rounded text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus ${sizeClasses[size]} ${variantClasses[variant]} ${className}`}
            {...props}
        />
    );
}
