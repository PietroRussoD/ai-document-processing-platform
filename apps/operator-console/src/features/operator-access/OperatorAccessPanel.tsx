import { useRef } from "react";

import { Button } from "../../components/ui/Button";
import { useOperatorToken } from "./operatorToken";

export function OperatorAccessPanel() {
    const { operatorToken, setOperatorToken } = useOperatorToken();
    const inputRef = useRef<HTMLInputElement>(null);
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
                Use the local demo token for PDF access, review decisions and
                reprocessing. It stays in memory while this Documents page is
                open and is cleared when you leave or reload it.
            </p>
            <div className="mt-4 flex flex-wrap items-end gap-3">
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
                            setOperatorToken(event.target.value)
                        }
                        spellCheck={false}
                        type="password"
                        value={operatorToken}
                    />
                </label>
                <Button
                    disabled={!operatorToken}
                    onClick={() => {
                        setOperatorToken("");
                        inputRef.current?.focus();
                    }}
                >
                    Clear token
                </Button>
            </div>
        </section>
    );
}
