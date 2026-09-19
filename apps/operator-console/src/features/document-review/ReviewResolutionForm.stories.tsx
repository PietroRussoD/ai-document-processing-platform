import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";

import { ReviewResolutionForm } from "./ReviewResolutionForm";

type StoryArgs = {
    errorMessage: string | null;
    isSaving: boolean;
};

const meta = {
    title: "Document review/ReviewResolutionForm",
    component: InteractiveReviewResolutionForm,
    tags: ["autodocs"],
    args: {
        errorMessage: null,
        isSaving: false,
    },
    argTypes: {
        errorMessage: {
            control: "text",
        },
        isSaving: {
            control: "boolean",
        },
    },
} satisfies Meta<typeof InteractiveReviewResolutionForm>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Ready: Story = {};

export const Saving: Story = {
    args: {
        isSaving: true,
    },
};

export const AuthenticationRejected: Story = {
    args: {
        errorMessage: "Review authentication was rejected.",
    },
};

function InteractiveReviewResolutionForm({
    errorMessage,
    isSaving,
}: StoryArgs) {
    const [operatorToken, setOperatorToken] = useState("");
    const [reviewNote, setReviewNote] = useState("");

    return (
        <ReviewResolutionForm
            errorMessage={errorMessage}
            invoiceExtraction={null}
            isSaving={isSaving}
            onDecision={() => undefined}
            onOperatorTokenChange={setOperatorToken}
            onReviewNoteChange={setReviewNote}
            operatorToken={operatorToken}
            reviewNote={reviewNote}
        />
    );
}
