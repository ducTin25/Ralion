import { WorkspaceStatePage } from "@/components/ui/WorkspaceStatePage";

export default function OnboardingPage() {
  return (
    <WorkspaceStatePage
      description="Onboarding plans are issued per membership. Open a project to see the checklist your PM approved."
      eyebrow="Project onboarding"
      icon="journey"
      primary={{ href: "/select-project", label: "Continue onboarding" }}
      title="Continue from a project workspace"
    />
  );
}
