import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";

export function StatsPage() {
  const { data, isLoading } = useQuery({ queryKey: ["stats"], queryFn: api.getStats });

  return (
    <div className="mx-auto max-w-md p-4">
      <header className="mb-6 flex items-center justify-between">
        <h1 className="pp-heading text-lg">Stats</h1>
        <Link to="/" className="pp-btn">
          Zurück
        </Link>
      </header>
      {isLoading ? (
        <p className="pp-heading text-center text-sm">Lade…</p>
      ) : (
        <div className="grid grid-cols-2 gap-3">
          <Stat label="Pflanzen" value={data?.total_plants ?? 0} />
          <Stat label="Durstig" value={data?.thirsty_count ?? 0} />
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="pp-frame flex flex-col items-center gap-2 p-6">
      <span className="text-3xl text-pp-gold">{value}</span>
      <span className="text-xs uppercase opacity-80">{label}</span>
    </div>
  );
}
