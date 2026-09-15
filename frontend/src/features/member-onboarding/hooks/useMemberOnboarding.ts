"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createMemberBlocker,
  getMemberChecklist,
  getMemberTask,
  listMemberBlockers,
  listMemberNotifications,
  listMemberProjects,
  updateMemberTaskStatus,
} from "@/features/member-onboarding/api";
import type {
  BlockerCategory,
  MemberBlocker,
  MemberChecklist,
  MemberTaskDetail,
  MemberTaskSummary,
  TaskStatus,
} from "@/features/member-onboarding/types";
import { memberQueryKeys } from "@/features/member-onboarding/queryClient";
import { ApiError } from "@/lib/api";

export function memberErrorMessage(
  error: unknown,
  fallback: string,
  statusMessages?: Partial<Record<401 | 403 | 404, string>>,
) {
  if (error instanceof ApiError) {
    if (error.status === 401)
      return statusMessages?.[401] ?? "Your session has expired. Please sign in again.";
    if (error.status === 403)
      return statusMessages?.[403] ?? "You do not have access to this data.";
    if (error.status === 404)
      return statusMessages?.[404] ?? "The requested data no longer exists.";
    return error.message;
  }
  return error instanceof Error ? error.message : fallback;
}

function toTaskSummary(task: MemberTaskDetail): MemberTaskSummary {
  return {
    plan_task_id: task.plan_task_id,
    title: task.title,
    category: task.category,
    display_order: task.display_order,
    mandatory: task.mandatory,
    estimated_minutes: task.estimated_minutes,
    status: task.status,
    due_at: task.due_at,
    is_overdue: task.is_overdue,
    is_due_soon: task.is_due_soon,
    started_at: task.started_at,
    completed_at: task.completed_at,
    dependencies_met: task.dependencies_met,
    open_blocker_count: task.open_blocker_count,
    source_count: task.source_count,
    is_locked: task.is_locked,
    lock_reason: task.lock_reason,
    can_start: task.can_start,
    can_complete: task.can_complete,
  };
}

function replaceChecklistTask(
  checklist: MemberChecklist | undefined,
  updated: MemberTaskDetail,
): MemberChecklist | undefined {
  if (!checklist) return checklist;
  const summary = toTaskSummary(updated);
  const groups = checklist.groups.map((group) => ({
    ...group,
    tasks: group.tasks.map((task) => (task.plan_task_id === updated.plan_task_id ? summary : task)),
  }));
  const mandatory = groups.flatMap((group) => group.tasks).filter((task) => task.mandatory);
  const completed = mandatory.filter((task) => task.status === "DONE").length;
  return {
    ...checklist,
    groups,
    progress: {
      completed,
      total: mandatory.length,
      percent: mandatory.length === 0 ? 0 : Math.round((completed / mandatory.length) * 100),
    },
  };
}

function addBlockerToChecklist(
  checklist: MemberChecklist | undefined,
  taskId: number,
): MemberChecklist | undefined {
  if (!checklist) return checklist;
  return {
    ...checklist,
    groups: checklist.groups.map((group) => ({
      ...group,
      tasks: group.tasks.map((task) =>
        task.plan_task_id === taskId
          ? {
              ...task,
              open_blocker_count: task.open_blocker_count + 1,
              can_complete: false,
            }
          : task,
      ),
    })),
  };
}

type UseMemberOnboardingOptions = {
  projectId: number | null;
  taskId: number | null;
};

export function useMemberOnboarding({ projectId, taskId }: UseMemberOnboardingOptions) {
  const queryClient = useQueryClient();

  const projectsQuery = useQuery({
    queryKey: memberQueryKeys.projects(),
    queryFn: ({ signal }) => listMemberProjects(signal),
  });
  const checklistQuery = useQuery({
    queryKey: memberQueryKeys.checklist(projectId ?? 0),
    queryFn: ({ signal }) => getMemberChecklist(projectId as number, signal),
    enabled: projectId !== null,
  });
  const blockersQuery = useQuery({
    queryKey: memberQueryKeys.blockers(projectId ?? 0),
    queryFn: ({ signal }) => listMemberBlockers(projectId as number, signal),
    enabled: projectId !== null,
  });
  const taskQuery = useQuery({
    queryKey: memberQueryKeys.task(taskId ?? 0),
    queryFn: ({ signal }) => getMemberTask(taskId as number, signal),
    enabled: taskId !== null,
  });
  const notificationsQuery = useQuery({
    queryKey: memberQueryKeys.notifications(projectId ?? 0),
    queryFn: ({ signal }) => listMemberNotifications(projectId as number, signal),
    enabled: projectId !== null,
    // Bell contents drift as due dates pass — refresh periodically instead of only on navigation.
    refetchInterval: 5 * 60_000,
  });

  const transitionMutation = useMutation({
    mutationFn: ({
      targetTaskId,
      status,
    }: {
      targetTaskId: number;
      targetProjectId: number;
      status: Extract<TaskStatus, "IN_PROGRESS" | "DONE">;
    }) => updateMemberTaskStatus(targetTaskId, status),
    onSuccess: (updated, { status, targetProjectId }) => {
      queryClient.setQueryData(memberQueryKeys.task(updated.plan_task_id), updated);
      queryClient.setQueryData<MemberChecklist>(
        memberQueryKeys.checklist(targetProjectId),
        (current) => replaceChecklistTask(current, updated),
      );
      // Completing a predecessor may unlock other tasks. Keep the immediate response in the
      // cache, then reconcile dependent rows in the background without blocking the action.
      if (status === "DONE") {
        void queryClient.invalidateQueries({
          queryKey: memberQueryKeys.checklist(targetProjectId),
        });
      }
    },
  });

  const blockerMutation = useMutation({
    mutationFn: ({
      targetTaskId,
      payload,
    }: {
      targetTaskId: number;
      targetProjectId: number;
      payload: { category: BlockerCategory; reason: string; attachments: File[] };
    }) => createMemberBlocker(targetTaskId, payload),
    onSuccess: (created, { targetTaskId, targetProjectId }) => {
      queryClient.setQueryData<MemberBlocker[]>(
        memberQueryKeys.blockers(targetProjectId),
        (current) => [
          created,
          ...(current ?? []).filter((blocker) => blocker.blocker_id !== created.blocker_id),
        ],
      );
      queryClient.setQueryData<MemberChecklist>(
        memberQueryKeys.checklist(targetProjectId),
        (current) => addBlockerToChecklist(current, targetTaskId),
      );
      queryClient.setQueryData<MemberTaskDetail>(memberQueryKeys.task(targetTaskId), (current) =>
        current
          ? {
              ...current,
              open_blocker_count: current.open_blocker_count + 1,
              can_complete: false,
            }
          : current,
      );
    },
  });

  const transitionTask = async (
    targetTaskId: number,
    status: Extract<TaskStatus, "IN_PROGRESS" | "DONE">,
  ) => {
    if (projectId === null) return null;
    try {
      return await transitionMutation.mutateAsync({
        targetTaskId,
        targetProjectId: projectId,
        status,
      });
    } catch {
      return null;
    }
  };

  const reportBlocker = async (
    targetTaskId: number,
    payload: { category: BlockerCategory; reason: string; attachments: File[] },
  ) => {
    if (projectId === null) return null;
    try {
      return await blockerMutation.mutateAsync({
        targetTaskId,
        targetProjectId: projectId,
        payload,
      });
    } catch {
      return null;
    }
  };

  return {
    projectData: projectsQuery.data ?? null,
    checklist: checklistQuery.data ?? null,
    taskDetail: taskQuery.data ?? null,
    blockers: blockersQuery.data ?? [],
    notifications: notificationsQuery.data ?? [],
    loadingProjects: projectsQuery.isPending,
    loadingChecklist: checklistQuery.isPending,
    loadingTask: taskQuery.isPending,
    updatingTask: transitionMutation.isPending,
    loadingBlockers: blockersQuery.isPending,
    creatingBlocker: blockerMutation.isPending,
    projectsError: projectsQuery.error,
    checklistError: checklistQuery.error,
    taskLoadError: taskQuery.error,
    taskActionError: transitionMutation.error,
    blockersLoadError: blockersQuery.error,
    blockerActionError: blockerMutation.error,
    refreshProjects: projectsQuery.refetch,
    refreshChecklist: checklistQuery.refetch,
    refreshBlockers: blockersQuery.refetch,
    transitionTask,
    reportBlocker,
  };
}
