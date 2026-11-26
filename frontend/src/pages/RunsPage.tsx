import { useState } from "react";
import { useQuery } from "../api/queries";
import type { Run } from "../api/schema";
import { Pagination, RunStatusBadge, StateView, unknown } from "../components/catalog";

function RunMetrics({ run }: { run: Run }) {
  const metrics = {
    "Páginas procesadas": run.pages_processed, Recibidos: run.received, Creados: run.created,
    Actualizados: run.updated, "Sin cambios": run.unchanged, Rechazados: run.rejected,
    Fallos: run.failures, Solicitudes: run.requests, "Duración (ms)": run.duration_ms,
    "Persistencia (ms)": run.persistence_ms,
  };

  return <>
    <p><RunStatusBadge status={run.status} /> {run.truncated && <strong>Truncada</strong>}</p>
    <dl>
      <dt>Inicio</dt><dd>{run.started_at}</dd>
      <dt>Fin</dt><dd>{run.finished_at ?? unknown}</dd>
      {Object.entries(metrics).map(([name, value]) => (
        <div key={name}><dt>{name}</dt><dd>{value ?? unknown}</dd></div>
      ))}
    </dl>
  </>;
}

export function RunsPage() {
  const [page, setPage] = useState(1);
  const runs = useQuery("listRuns", { page });
  return <>
    <h1>Ejecuciones</h1>
    <StateView query={runs} empty={data => data.total === 0}>{data => <>
      <div className="results">{data.items.map(run => <article key={run.id}>
        <h2><a href={`/runs/${run.id}`}>{run.source_id}</a></h2>
        <RunMetrics run={run} />
      </article>)}</div>
      <Pagination value={data} onPage={setPage} />
    </>}</StateView>
  </>;
}

export function RunPage({ runId }: { runId: string }) {
  const run = useQuery("getRun", { runId });
  return <StateView query={run}>{data => <>
    <h1>Ejecución de {data.source_id}</h1>
    <RunMetrics run={data} />
    <h2>Consultas</h2>
    <ul>{data.queries.map(query => <li key={query.query_index}>
      {query.term ?? unknown} · {query.pages_processed} páginas · Total declarado: {query.total_declared ?? unknown}
      {query.truncated && " · Truncada"}
    </li>)}</ul>
    <h2>Errores</h2>
    {data.errors.length ? <ul>{data.errors.map((error, index) => (
      <li key={index}>{error.code}: {error.message} · HTTP {error.http_status ?? unknown}
        {" · Intentos: "}{error.attempts ?? unknown}</li>
    ))}</ul> : <p>Sin errores registrados.</p>}
    <h2>Motivos de rechazo</h2>
    {data.rejection_reasons === null ? <p>{unknown}</p> :
      Object.entries(data.rejection_reasons).length ? <ul>{
        Object.entries(data.rejection_reasons).map(([reason, count]) => <li key={reason}>{reason}: {count}</li>)
      }</ul> : <p>Sin rechazos.</p>}
  </>}</StateView>;
}
