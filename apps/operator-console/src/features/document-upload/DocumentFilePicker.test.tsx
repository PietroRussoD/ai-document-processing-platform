import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { DocumentFilePicker } from "./DocumentFilePicker";

test("shows and clears a selected PDF", () => {
    render(<DocumentFilePicker />);
    const input = screen.getByLabelText("Choose a PDF");

    fireEvent.change(input, {
        target: {
            files: [
                new File(["pdf"], "invoice.pdf", { type: "application/pdf" }),
            ],
        },
    });

    expect(screen.getByText("invoice.pdf")).toBeVisible();
    expect(screen.getByText("3 B")).toBeVisible();

    fireEvent.click(
        screen.getByRole("button", { name: "Remove selected document" }),
    );
    expect(screen.queryByText("invoice.pdf")).not.toBeInTheDocument();

    fireEvent.change(input, {
        target: {
            files: [
                new File([new Uint8Array(2048)], "purchase-order.pdf", {
                    type: "application/pdf",
                }),
            ],
        },
    });
    expect(screen.getByText("2.0 KiB")).toBeVisible();
});

test("rejects non-PDF files", () => {
    render(<DocumentFilePicker />);

    fireEvent.change(screen.getByLabelText("Choose a PDF"), {
        target: {
            files: [new File(["text"], "notes.txt", { type: "text/plain" })],
        },
    });

    expect(screen.getByRole("alert")).toHaveTextContent(
        "Select a PDF document.",
    );
    expect(screen.queryByText("notes.txt")).not.toBeInTheDocument();
});

test("rejects files larger than the client limit", () => {
    render(<DocumentFilePicker />);
    const oversizedPdf = new File(["pdf"], "large.pdf", {
        type: "application/pdf",
    });
    Object.defineProperty(oversizedPdf, "size", {
        value: 20 * 1024 * 1024 + 1,
    });

    fireEvent.change(screen.getByLabelText("Choose a PDF"), {
        target: { files: [oversizedPdf] },
    });

    expect(screen.getByRole("alert")).toHaveTextContent(
        "must not exceed 20 MiB",
    );
});
