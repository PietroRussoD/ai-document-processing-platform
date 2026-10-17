import { useEffect, useRef, useState, type FormEvent } from "react";

import { Button } from "../../components/ui/Button";
import { useOperatorToken } from "./operatorToken";

type OperatorAccessPanelProps = {
    onConnect?: (token: string) => Promise<void>;
    onDisconnect?: () => void;
    isConnecting?: boolean;
    connectionError?: string | null;
};

export function OperatorAccessPanel({
    onConnect,
    onDisconnect,
    isConnecting = false,
    connectionError = null,
}: OperatorAccessPanelProps) {
    const { operatorToken, setOperatorToken, isConnected, setIsConnected } =
        useOperatorToken();
    const inputRef = useRef<HTMLInputElement>(null);
    const wasConnected = useRef(isConnected);
    const [draftToken, setDraftToken] = useState(operatorToken);

    useEffect(() => {
        if (wasConnected.current && !isConnected) {
            inputRef.current?.focus();
        }
        wasConnected.current = isConnected;
    }, [isConnected]);

    function submit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        const connect =
            onConnect ??
            (async (token: string) => {
                setOperatorToken(token);
                setIsConnected(true);
            });
        void connect(draftToken);
    }

    function disconnect() {
        onDisconnect?.();
        setOperatorToken("");
        setIsConnected(false);
        setDraftToken("");
    }

    return (
        <section
            aria-labelledby="operator-access-heading"
            className="mb-6 border border-app-border bg-app-surface p-5"
        >
            <h2
                id="operator-access-heading"
                className="text-base font-semibold"
            >
                Operator access
            </h2>
            <p
                id="operator-access-help"
                className="mt-2 text-sm text-app-muted"
            >
                Enter the local operator token to open document queues and
                details. It stays in memory while this page is open and clears
                when you leave or reload it.
            </p>
            {isConnected ? (
                <div className="mt-4 flex flex-wrap items-center gap-3">
                    <p className="text-sm text-app-muted" role="status">
                        Operator token accepted.
                    </p>
                    <Button onClick={disconnect} type="button">
                        Clear token
                    </Button>
                </div>
            ) : (
                <form
                    className="mt-4 flex flex-wrap items-end gap-3"
                    onSubmit={submit}
                >
                    <label
                        className="block w-full max-w-md text-sm font-medium text-app-foreground"
                        htmlFor="operator-token"
                    >
                        Operator token
                        <input
                            ref={inputRef}
                            id="operator-token"
                            aria-describedby="operator-access-help"
                            autoComplete="off"
                            className="mt-1.5 h-10 w-full rounded border border-app-border-strong bg-app-surface px-3 font-mono text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-app-focus"
                            onChange={(event) =>
                                setDraftToken(event.target.value)
                            }
                            spellCheck={false}
                            type="password"
                            value={draftToken}
                        />
                    </label>
                    <Button
                        disabled={!draftToken || isConnecting}
                        type="submit"
                    >
                        {isConnecting ? "Checking token" : "Open documents"}
                    </Button>
                </form>
            )}
            {connectionError !== null ? (
                <p className="mt-3 text-sm text-app-danger" role="alert">
                    {connectionError}
                </p>
            ) : null}
        </section>
    );
}
