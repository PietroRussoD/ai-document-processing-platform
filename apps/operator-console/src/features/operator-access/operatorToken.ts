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
};

export const OperatorTokenContext = createContext<OperatorTokenState | null>(
    null,
);

export function useOperatorToken() {
    const shared = useContext(OperatorTokenContext);
    const [operatorToken, setOperatorToken] = useState("");
    return {
        ...(shared ?? { operatorToken, setOperatorToken }),
        isShared: shared !== null,
    };
}
