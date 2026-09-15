import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { RepoScanWizard } from "@/features/project-management/components/documents/RepoScanWizard";
import { filterCandidateFilesInBatches } from "@/features/project-management/components/documents/clientFileFilter";
import { requestEmbeddingWarmup } from "@/lib/embeddingWarmup";

vi.mock("@/features/project-management/api", () => ({
  importScanSelection: vi.fn(),
  scanRepository: vi.fn(),
}));
vi.mock("@/lib/embeddingWarmup", () => ({ requestEmbeddingWarmup: vi.fn() }));

describe("RepoScanWizard", () => {
  it("filters a large folder in yielding batches and reports progress", async () => {
    const paths = [
      "project/README.md",
      "project/src/main.ts",
      "project/docs/setup.txt",
      "project/node_modules/pkg/readme.md",
      "project/.env",
    ];
    const files = paths.map((path) => {
      const file = new File(["content"], path.split("/").at(-1) ?? "file");
      Object.defineProperty(file, "webkitRelativePath", { value: path });
      return file;
    });
    const progress: number[] = [];

    const candidates = await filterCandidateFilesInBatches(
      files,
      (processed) => progress.push(processed),
      2,
    );

    expect(candidates.map((file) => file.webkitRelativePath)).toEqual([
      "project/README.md",
      "project/docs/setup.txt",
    ]);
    expect(progress).toEqual([2, 4, 5]);
  });

  it("warms the scale-to-zero embedder without blocking the scanner when warm-up fails", async () => {
    vi.mocked(requestEmbeddingWarmup).mockRejectedValueOnce(new Error("embedding unavailable"));

    render(<RepoScanWizard projectId={9} onClose={vi.fn()} onImported={vi.fn()} />);

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Quét repository" })).toBeInTheDocument();
    await waitFor(() => expect(requestEmbeddingWarmup).toHaveBeenCalledTimes(1));
  });
});
