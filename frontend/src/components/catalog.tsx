import type { FormEvent, ReactNode } from "react";
import type { Query } from "../api/queries";
import type { Attribution as DatasetAttribution, DatasetSummary, License, Locator, PageMeta, RunStatus } from "../api/schema";

export const unknown = "Desconocido";

export function StateView<T>({ query, empty, children }: {
  query: Query<T>; empty?: (data: T) => boolean; children: (data: T) => ReactNode;
}) {
  if (query.state === "ready") {
    return empty?.(query.data) ? <p role="status">Sin resultados.</p> : children(query.data);
  }
  if (query.state === "missing") return <p role="status">Recurso no encontrado.</p>;
  if (query.state === "failed") return <p role="alert">No se pudo cargar la información.</p>;
  return <p role="status">Cargando…</p>;
}

export function SafeLink({ url, children }: { url: string | null; children?: ReactNode }) {
  if (!url) return <>{children ?? unknown}</>;
  try {
    const parsed = new URL(url);
    if (/^https:\/\//i.test(url) && parsed.protocol === "https:" && !parsed.username && !parsed.password) {
      return <a href={parsed.href} rel="noopener noreferrer">{children ?? url}</a>;
    }
  } catch {
    // A malformed locator is presented as text.
  }
  return <>{children ?? url}</>;
}

export function LicenseList({ licenses }: { licenses: License[] }) {
  if (!licenses.length) return <p>Licencia: {unknown}</p>;
  return <ul aria-label="Licencias">{licenses.map(({name, url, note}, index) => (
    <li key={index}><SafeLink url={url}>{name ?? url ?? unknown}</SafeLink>{note && <> · {note}</>}</li>
  ))}</ul>;
}

export function Attribution({ value }: { value: DatasetAttribution }) {
  return <dl>
    <dt>Atribución</dt><dd>{value.text ?? unknown}</dd>
    <dt>Fuentes de los datos</dt><dd>{value.data_sources.join(", ") || unknown}</dd>
    <dt>Fecha de actualización de los datos</dt><dd>{value.data_updated_at ?? unknown}</dd>
    <dt>Requisito de cita</dt><dd>{value.citation_requirement ?? unknown}</dd>
  </dl>;
}

export function LocatorList({ locators }: { locators: Locator[] }) {
  if (!locators.length) return <p>{unknown}</p>;
  return <ul>{locators.map(({ kind, url, status, source_field }) => (
    <li key={JSON.stringify([kind, url, source_field])}>{kind} · {source_field} · {status === "invalid" ? "Inválido" : "Sin verificar"} · {
      status === "invalid" ? url : <SafeLink url={url} />
    }</li>
  ))}</ul>;
}

export function Review({ status }: { status: DatasetSummary["review_status"] }) {
  return <span>{status === "verified" ? "Verificado" : "Revisión pendiente"}</span>;
}

export function DatasetCard({ dataset }: { dataset: DatasetSummary }) {
  return <article>
    <h2><a href={`/datasets/${dataset.id}`}>{dataset.title}</a></h2>
    <p>{dataset.provider} · {dataset.platform} · <Review status={dataset.review_status} /></p>
    <p>{dataset.description ?? unknown}</p>
    <LicenseList licenses={dataset.licenses} />
    <Attribution value={dataset.attribution} />
  </article>;
}

const runLabels: Record<RunStatus, string> = {
  running: "En curso", succeeded: "Exitosa", partial: "Parcial", failed: "Fallida",
};

export function RunStatusBadge({ status }: { status: RunStatus }) {
  return <strong className="run-status" data-status={status}>{runLabels[status]}</strong>;
}

export function Pagination({ value, onPage }: { value: PageMeta; onPage: (n: number) => void }) {
  return <nav className="pagination" aria-label="Paginación">
    <button disabled={value.page <= 1} onClick={() => onPage(value.page - 1)}>Anterior</button>
    <span>Página {value.page} · {value.total} resultados</span>
    <button disabled={value.page >= 10000 || value.page * value.page_size >= value.total}
      onClick={() => onPage(value.page + 1)}>Siguiente</button>
  </nav>;
}

export interface SearchFilters { q: string; provider: string; category: string }

export function Filters({ providers, categories, onSearch }: {
  providers: string[]; categories: string[]; onSearch: (filters: SearchFilters) => void;
}) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    onSearch({
      q: String(form.get("q") ?? ""),
      provider: String(form.get("provider") ?? ""),
      category: String(form.get("category") ?? ""),
    });
  }
  return <form className="filters" onSubmit={submit} aria-label="Buscar datasets">
    <label>Búsqueda<input name="q" maxLength={200} type="search" /></label>
    <label>Proveedor<input name="provider" maxLength={200} list="providers" /></label>
    <datalist id="providers">{providers.map(value => <option key={value} value={value} />)}</datalist>
    <label>Categoría<input name="category" maxLength={200} list="categories" /></label>
    <datalist id="categories">{categories.map(value => <option key={value} value={value} />)}</datalist>
    <button>Buscar</button>
  </form>;
}
