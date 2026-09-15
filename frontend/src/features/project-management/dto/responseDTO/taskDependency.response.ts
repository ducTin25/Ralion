/** Response body trả về từ /api/v1/task-dependencies/pm[...]. */
export type TaskDependencyResponseDTO = {
  dependency_id: number;
  predecessor_task_id: number;
  successor_task_id: number;
};
