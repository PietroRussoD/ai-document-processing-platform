import { useMemo, useState, type PropsWithChildren } from "react";

import { OperatorTokenContext } from "./operatorToken";

export function OperatorTokenProvider({ children }: PropsWithChildren) {
    const [operatorToken, setOperatorToken] = useState("");
    const [isConnected, setIsConnected] = useState(false);
    const value = useMemo(
        () => ({
            operatorToken,
            setOperatorToken,
            isConnected,
            setIsConnected,
        }),
        [operatorToken, isConnected],
    );
    return (
        <OperatorTokenContext.Provider value={value}>
            {children}
        </OperatorTokenContext.Provider>
    );
}
