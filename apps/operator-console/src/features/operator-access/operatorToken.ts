import {
    createContext,
    useContext,
    useState,
    type Dispatch,
    type SetStateAction,
} from "react";

type OperatorTokenState = {
    operatorToken: string;
    setOperatorToken: Dispatch<SetStateAction<string>>;
    isConnected: boolean;
    setIsConnected: Dispatch<SetStateAction<boolean>>;
};

export const OperatorTokenContext = createContext<OperatorTokenState | null>(
    null,
);

export function useOperatorToken() {
    const shared = useContext(OperatorTokenContext);
    const [operatorToken, setOperatorToken] = useState("");
    const [isConnected, setIsConnected] = useState(false);
    return {
        ...(shared ?? {
            operatorToken,
            setOperatorToken,
            isConnected,
            setIsConnected,
        }),
        isShared: shared !== null,
    };
}
