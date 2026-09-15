"use client";

import { useCallback, useEffect, useState } from "react";

import type { ProjectResponseDTO } from "@/features/project-management/dto/responseDTO/project.response";
import type { ProjectMembershipDetailResponseDTO } from "@/features/project-management/dto/responseDTO/projectMembership.response";
import type { PmBlockerResponseDTO } from "@/features/project-management/dto/responseDTO/blocker.response";
import {
  listProjectBlockers,
  listProjectMembers,
  listProjectsManagedByPm,
  resolveProjectBlocker,
} from "@/features/project-management/api";

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError";
}

export function useProjectManagement(requestedProjectId: number | null, enabled = true) {
  const [projects, setProjects] = useState<ProjectResponseDTO[]>([]);
  const [members, setMembers] = useState<ProjectMembershipDetailResponseDTO[]>([]);
  const [blockers, setBlockers] = useState<PmBlockerResponseDTO[]>([]);
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [loadingMembers, setLoadingMembers] = useState(false);
  const [loadingBlockers, setLoadingBlockers] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshProjects = useCallback(async (signal?: AbortSignal) => {
    setLoadingProjects(true);
    setError(null);
    try {
      const data = await listProjectsManagedByPm(signal);
      if (signal?.aborted) return;
      setProjects(data);
    } catch (err) {
      if (signal?.aborted || isAbortError(err)) return;
      setError(err instanceof Error ? err.message : "Projects could not be loaded");
    } finally {
      if (!signal?.aborted) setLoadingProjects(false);
    }
  }, []);

  const selectedProjectId =
    requestedProjectId !== null &&
    projects.some((project) => project.project_id === requestedProjectId)
      ? requestedProjectId
      : (projects[0]?.project_id ?? null);

  const refreshMembers = useCallback(async (projectId: number, signal?: AbortSignal) => {
    setLoadingMembers(true);
    try {
      const data = await listProjectMembers(projectId, signal);
      if (signal?.aborted) return;
      setMembers(data);
    } catch (err) {
      if (signal?.aborted || isAbortError(err)) return;
      setError(err instanceof Error ? err.message : "Members could not be loaded");
    } finally {
      if (!signal?.aborted) setLoadingMembers(false);
    }
  }, []);

  const refreshBlockers = useCallback(async (projectId: number, signal?: AbortSignal) => {
    setLoadingBlockers(true);
    try {
      const data = await listProjectBlockers(projectId, signal);
      if (signal?.aborted) return;
      setBlockers(data);
    } catch (err) {
      if (signal?.aborted || isAbortError(err)) return;
      setError(err instanceof Error ? err.message : "Blockers could not be loaded");
    } finally {
      if (!signal?.aborted) setLoadingBlockers(false);
    }
  }, []);

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    // Fetch data khi mount — pattern hợp lệ theo react.dev/learn/you-might-not-need-an-effect
    // (đồng bộ với external system/API), rule set-state-in-effect chỉ nhận diện được setState
    // gọi trực tiếp trong effect, không theo dõi được qua hàm useCallback tách riêng.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refreshProjects(controller.signal);
    return () => controller.abort();
  }, [enabled, refreshProjects]);

  useEffect(() => {
    if (enabled && selectedProjectId !== null) {
      const controller = new AbortController();
      // eslint-disable-next-line react-hooks/set-state-in-effect
      void refreshMembers(selectedProjectId, controller.signal);
      return () => controller.abort();
    }
  }, [enabled, selectedProjectId, refreshMembers]);

  useEffect(() => {
    if (enabled && selectedProjectId !== null) {
      const controller = new AbortController();
      // eslint-disable-next-line react-hooks/set-state-in-effect
      void refreshBlockers(selectedProjectId, controller.signal);
      return () => controller.abort();
    }
    setBlockers([]);
    return undefined;
  }, [enabled, selectedProjectId, refreshBlockers]);

  const resolveBlocker = useCallback(
    async (blockerId: number) => {
      if (selectedProjectId === null) return;
      await resolveProjectBlocker(selectedProjectId, blockerId);
      await refreshBlockers(selectedProjectId);
    },
    [refreshBlockers, selectedProjectId],
  );

  return {
    projects,
    selectedProjectId,
    members,
    blockers,
    loadingProjects,
    loadingMembers,
    loadingBlockers,
    error,
    refreshBlockers,
    resolveBlocker,
  };
}
