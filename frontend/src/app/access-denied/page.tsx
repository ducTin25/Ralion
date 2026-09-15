import { WorkspaceStatePage } from "@/components/ui/WorkspaceStatePage";
import { getTranslations } from "next-intl/server";

export default async function AccessDeniedPage() {
  const t = await getTranslations("accessDenied");
  return (
    <WorkspaceStatePage
      description={t("description")}
      eyebrow={t("eyebrow")}
      icon="lock"
      primary={{ href: "/select-project", label: t("primary") }}
      secondary={{
        href: "mailto:admin@onboarding.dev",
        label: t("secondary"),
        external: true,
      }}
      title={t("title")}
      tone="critical"
    />
  );
}
