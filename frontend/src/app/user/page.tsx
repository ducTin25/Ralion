import { dehydrate } from "@tanstack/react-query";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { getLocale } from "next-intl/server";
import { Suspense } from "react";

import { MemberPortal } from "@/features/member-onboarding/components/MemberPortal";
import {
  getMemberChecklist,
  getMemberTask,
  listMemberBlockers,
  listMemberProjects,
} from "@/features/member-onboarding/api";
import { createMemberQueryClient, memberQueryKeys } from "@/features/member-onboarding/queryClient";
import { localizePath, type Locale } from "@/i18n/routing";

export const dynamic = "force-dynamic";

type UserPageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

function positiveInteger(value: string | string[] | undefined) {
  const candidate = Array.isArray(value) ? value[0] : value;
  if (!candidate || !/^\d+$/.test(candidate)) return null;
  const parsed = Number(candidate);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null;
}

export default async function UserPage({ searchParams }: UserPageProps) {
  const params = await searchParams;
  const projectId = positiveInteger(params.project);
  if (projectId === null) {
    const locale = (await getLocale()) as Locale;
    redirect(localizePath("/select-project", locale));
  }

  const sessionCookie = (await cookies()).get("ralion_session")?.value;
  const serverAuth: RequestInit = sessionCookie
    ? { headers: { Cookie: `ralion_session=${sessionCookie}` } }
    : {};
  const taskId = positiveInteger(params.task);
  const queryClient = createMemberQueryClient();
  const prefetches: Promise<void>[] = [
    queryClient.prefetchQuery({
      queryKey: memberQueryKeys.projects(),
      queryFn: ({ signal }) => listMemberProjects(signal, serverAuth),
    }),
  ];
  if (projectId !== null) {
    prefetches.push(
      queryClient.prefetchQuery({
        queryKey: memberQueryKeys.checklist(projectId),
        queryFn: ({ signal }) => getMemberChecklist(projectId, signal, serverAuth),
      }),
      queryClient.prefetchQuery({
        queryKey: memberQueryKeys.blockers(projectId),
        queryFn: ({ signal }) => listMemberBlockers(projectId, signal, serverAuth),
      }),
    );
  }
  if (taskId !== null) {
    prefetches.push(
      queryClient.prefetchQuery({
        queryKey: memberQueryKeys.task(taskId),
        queryFn: ({ signal }) => getMemberTask(taskId, signal, serverAuth),
      }),
    );
  }
  await Promise.all(prefetches);

  return (
    <Suspense fallback={null}>
      <MemberPortal dehydratedState={dehydrate(queryClient)} />
    </Suspense>
  );
}
