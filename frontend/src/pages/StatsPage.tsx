import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { useI18n } from "../i18n";
import { ErrorState } from "../components/Feedback";

export function StatsPage() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const { data, isLoading, isError } = useQuery({ queryKey: ["stats"], queryFn: api.getStats });

  return (
    <div className="mx-auto max-w-md p-4">
      {/* No back button — the persistent TabBar is the sole primary navigation (Instagram-style). */}
      <header className="mb-6">
        <h1 className="pp-heading text-lg" tabIndex={-1}>
          {t("nav.stats")}
        </h1>
      </header>
      {isLoading ? (
        <p className="pp-heading text-center text-sm">{t("app.loading")}</p>
      ) : isError ? (
        <ErrorState onRetry={() => qc.invalidateQueries({ queryKey: ["stats"] })} />
      ) : !data || data.total_plants === 0 ? (
        <div className="pp-frame p-8 text-center text-sm">
          <div className="mb-3 text-4xl" aria-hidden="true">
            📊
          </div>
          <p className="pp-heading mb-2 text-sm">{t("stats.empty.title")}</p>
          <p className="mb-4 opacity-70">{t("stats.empty.hint")}</p>
          <Link to="/" className="pp-btn">
            {t("empty.cta")}
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-3">
          <Stat label={t("stats.totalPlants")} value={String(data.total_plants)} />
          <Stat label={t("stats.thirsty")} value={String(data.thirsty_count)} />
          <Stat label={t("stats.streak")} value={String(data.watering_streak_days)} />
          <Stat label={t("stats.consistency")} value={`${data.watering_consistency_pct}%`} />
          <div className="col-span-2">
            <Stat
              detail
              label={t("stats.longestOverdue")}
              value={
                data.longest_overdue
                  ? `${data.longest_overdue.name} (${data.longest_overdue.days_overdue}d)`
                  : t("stats.none")
              }
            />
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  detail = false,
}: {
  label: string;
  value: string;
  detail?: boolean;
}) {
  // A narrative string (e.g. "Monstera (14d)") doesn't belong in the big-number KPI slot — render
  // it as a left-aligned group-list row so it can't read as the most prominent stat or overflow.
  if (detail) {
    return (
      <div className="pp-frame flex flex-col gap-1 p-4">
        <span className="text-[11px] uppercase opacity-70">{label}</span>
        <span className="break-words text-sm font-semibold text-pp-gold">{value}</span>
      </div>
    );
  }
  // Label is FIRST in the DOM (VoiceOver reads "Plants" then "42"); flex-col-reverse keeps the big
  // number visually on top. 11px lifts the label off the readability floor of Press Start 2P.
  return (
    <div className="pp-frame flex flex-col-reverse items-center gap-2 p-6 text-center">
      <span className="text-[11px] uppercase opacity-80">{label}</span>
      <span className="break-words text-2xl font-bold text-pp-gold">{value}</span>
    </div>
  );
}
