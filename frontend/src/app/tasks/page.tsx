import { WorkspaceStatePage } from "@/components/ui/WorkspaceStatePage";

export default function TasksPage() {
  return (
    <WorkspaceStatePage
      description="Your checklist and progress live in the Engineer Portal, scoped to your active project membership."
      eyebrow="Checklist & Plan"
      icon="tasks"
      primary={{ href: "/select-project", label: "Open my project" }}
      title="Tasks live inside a project workspace"
    />
  );
}
