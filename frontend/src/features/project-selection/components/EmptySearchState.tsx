import { useTranslations } from "next-intl";

export function EmptySearchState({ onClear }: { onClear: () => void }) {
  const t = useTranslations("projectSelection");
  return (
    <div className="rounded-lg border border-border bg-surface px-6 py-[52px] text-center">
      <h2 className="text-base font-semibold text-text">{t("noMatchTitle")}</h2>
      <p className="mt-1.5 text-sm leading-6 text-text-subtle">{t("noMatchBody")}</p>
      <button
        type="button"
        onClick={onClear}
        className="mt-5 h-10 rounded-md border border-border-strong bg-surface px-4 text-sm font-semibold text-navy hover:bg-canvas focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-link max-md:h-11"
      >
        {t("clearFilters")}
      </button>
    </div>
  );
}
