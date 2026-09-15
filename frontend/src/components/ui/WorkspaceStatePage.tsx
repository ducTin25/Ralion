import { useTranslations } from "next-intl";
import { FileIcon, LockIcon, MilestoneIcon, TasklistIcon } from "@primer/octicons-react";

import { LogoutButton } from "@/components/auth/LogoutButton";
import { RalionBrand } from "@/components/brand/RalionBrand";
import { LanguageSwitcher } from "@/components/i18n/LanguageSwitcher";
import { Link } from "@/i18n/navigation";

type StateTone = "accent" | "critical";
type StateIcon = "document" | "tasks" | "journey" | "lock";

type WorkspaceStatePageProps = {
  eyebrow: string;
  title: string;
  description: string;
  icon: StateIcon;
  tone?: StateTone;
  primary: { href: string; label: string };
  secondary?: { href: string; label: string; external?: boolean };
};

function StateGlyph({ icon }: { icon: StateIcon }) {
  const Icon =
    icon === "document"
      ? FileIcon
      : icon === "tasks"
        ? TasklistIcon
        : icon === "journey"
          ? MilestoneIcon
          : LockIcon;
  return <Icon aria-hidden="true" size={20} />;
}

export function WorkspaceStatePage({
  eyebrow,
  title,
  description,
  icon,
  tone = "accent",
  primary,
  secondary,
}: WorkspaceStatePageProps) {
  const t = useTranslations("common");
  const critical = tone === "critical";
  const iconClass = critical
    ? "border-critical-border bg-critical-bg text-critical"
    : "border-accent bg-accent-bg text-accent";

  return (
    <main className="min-h-screen bg-canvas text-text">
      <header className="flex h-[58px] items-center justify-between border-b border-border bg-surface px-5 sm:px-7">
        <RalionBrand size={28} />
        <div className="flex items-center gap-2">
          <LanguageSwitcher className="hidden sm:inline-flex" compact />
          <Link
            className="rounded-[5px] px-2 py-2 text-[13px] font-semibold text-accent hover:bg-accent-bg hover:no-underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            href="/select-project"
          >
            {t("workspace")}
          </Link>
          <LogoutButton className="h-9 rounded-md border border-border-strong bg-surface px-3 text-[13px] font-semibold text-text-secondary hover:bg-surface-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent" />
        </div>
      </header>

      <div className="mx-auto flex max-w-[760px] px-5 py-12 sm:py-20">
        <section className="w-full rounded-lg border border-border bg-surface p-6 shadow-sm sm:p-8">
          <span
            className={`inline-flex h-10 w-10 items-center justify-center rounded-md border ${iconClass}`}
          >
            <StateGlyph icon={icon} />
          </span>
          <p
            className={`mt-5 text-[11px] font-bold uppercase tracking-[0.08em] ${critical ? "text-critical" : "text-accent"}`}
          >
            {eyebrow}
          </p>
          <h1 className="mt-1.5 text-[22px] font-bold leading-7 tracking-[-0.01em]">{title}</h1>
          <p className="mt-2 max-w-2xl text-[13.5px] leading-6 text-text-subtle">{description}</p>

          <div className="mt-6 flex flex-wrap gap-2.5">
            <Link
              className="inline-flex h-10 items-center rounded-md border border-accent bg-accent px-4 text-[13px] font-semibold text-white hover:bg-accent-hover hover:no-underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
              href={primary.href}
            >
              {primary.label}
            </Link>
            {secondary &&
              (secondary.external ? (
                <a
                  className="inline-flex h-10 items-center rounded-md border border-border-strong bg-surface px-4 text-[13px] font-semibold text-text hover:bg-surface-2 hover:no-underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                  href={secondary.href}
                >
                  {secondary.label}
                </a>
              ) : (
                <Link
                  className="inline-flex h-10 items-center rounded-md border border-border-strong bg-surface px-4 text-[13px] font-semibold text-text hover:bg-surface-2 hover:no-underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                  href={secondary.href}
                >
                  {secondary.label}
                </Link>
              ))}
          </div>
        </section>
      </div>
    </main>
  );
}
