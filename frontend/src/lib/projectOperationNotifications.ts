export const PROJECT_OPERATION_COMPLETED_EVENT = "ralion:project-operation-completed";

export type ProjectOperationType =
  | "DOCUMENT_UPLOAD"
  | "REPOSITORY_IMPORT"
  | "GITHUB_SYNC"
  | "CONVENTION_DISCOVERY";

export type ProjectOperationStatus = "SUCCEEDED" | "FAILED";

export type ProjectOperationCompletedDetail = {
  projectId: number;
  operation: ProjectOperationType;
  status: ProjectOperationStatus;
  completedAt: string;
  title?: string;
  repo?: string | null;
  documentsImported?: number;
  familiesCreated?: number;
  familiesUpdated?: number;
  errorSummary?: string | null;
};

export function notifyProjectOperationCompleted(detail: ProjectOperationCompletedDetail) {
  window.dispatchEvent(
    new CustomEvent<ProjectOperationCompletedDetail>(PROJECT_OPERATION_COMPLETED_EVENT, { detail }),
  );
}
