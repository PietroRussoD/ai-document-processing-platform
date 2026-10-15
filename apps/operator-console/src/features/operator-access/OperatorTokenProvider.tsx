import { useMemo, useState, type PropsWithChildren } from "react";

import { OperatorTokenContext } from "./operatorToken";

export function OperatorTokenProvider({ children }: PropsWithChildren) {
    const [operatorToken, setOperatorToken] = useState("");
    const value = useMemo(
        () => ({ operatorToken, setOperatorToken }),
        [operatorToken],
    );
    return (
        <OperatorTokenContext.Provider value={value}>
            {children}
        </OperatorTokenContext.Provider>
    );
}
