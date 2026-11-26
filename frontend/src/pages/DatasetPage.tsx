import { useState } from "react";
import { useQuery } from "../api/queries";
import type { Observation } from "../api/schema";
import { Attribution, LicenseList, LocatorList, Pagination, Review, SafeLink, StateView, unknown } from "../components/catalog";

function Observations({ items }: { items: Observation[] }) {
  if (!items.length) return <p>Sin observaciones.</p>;
  return <ul>{items.map(item => (
    <li key={JSON.stringify(item)}>{item.observed_at} · {item.query_term ?? unknown}
      {" · "}<SafeLink url={item.source_url} />{" · "}<a href={`/runs/${item.run_id}`}>Ver ejecución</a>
    </li>
  ))}</ul>;
}

function FullProvenance({ datasetId }: { datasetId: string }) {
  const [page, setPage] = useState(1);
  const observations = useQuery("listDatasetProvenance", { datasetId, page });
  return <StateView query={observations}>{data => <>
    <Observations items={data.items} /><Pagination value={data} onPage={setPage} />
  </>}</StateView>;
}

export function DatasetPage({ datasetId }: { datasetId: string }) {
  const dataset = useQuery("getDataset", { datasetId });
  const [full, setFull] = useState(false);

  return <StateView query={dataset}>{data => <>
    <h1>{data.title}</h1>
    <p>{data.provider} · {data.platform} · <Review status={data.review_status} /></p>
    <p>{data.description ?? unknown}</p>
    <dl>
      <dt>Identificador externo</dt><dd>{data.external_id}</dd>
      <dt>Publicador</dt><dd>{data.publisher ?? unknown}</dd>
      <dt>Categorías</dt><dd>{data.categories.join(", ") || unknown}</dd>
      <dt>Temas</dt><dd>{data.topics.join(", ") || unknown}</dd>
      <dt>Etiquetas</dt><dd>{data.tags.join(", ") || unknown}</dd>
      <dt>URL del dataset</dt><dd><SafeLink url={data.official_url} /></dd>
      <dt>Creación</dt><dd>{data.created_at ?? unknown}</dd>
      <dt>Publicación</dt><dd>{data.published_at ?? unknown}</dd>
      <dt>Actualización</dt><dd>{data.updated_at ?? unknown}</dd>
      <dt>Actualización de metadatos</dt><dd>{data.metadata_updated_at ?? unknown}</dd>
      <dt>Primera observación</dt><dd>{data.first_seen_at}</dd>
      <dt>Última observación</dt><dd>{data.last_seen_at}</dd>
      <dt>Permiso de extracción</dt><dd>{data.extraction_permission}</dd>
      <dt>Permiso de redistribución</dt><dd>{data.redistribution_permission}</dd>
      <dt>Condiciones de acceso del dataset</dt><dd>{data.access_conditions ?? unknown}</dd>
      <dt>Condiciones de redistribución del dataset</dt><dd>{data.redistribution_conditions ?? unknown}</dd>
    </dl>
    <h2>Licencias del dataset</h2>
    <LicenseList licenses={data.licenses} />
    <Attribution value={data.attribution} />
    <h2>Fuente</h2>
    <dl>
      <dt>Sitio oficial</dt><dd><SafeLink url={data.source.official_url} /></dd>
      <dt>Fecha de verificación</dt><dd>{data.source.verified_at}</dd>
      <dt>Licencia de la fuente</dt><dd><SafeLink url={data.source.license_url}>
        {data.source.license_name ?? data.source.license_url ?? unknown}
      </SafeLink></dd>
      <dt>Condiciones de acceso de la fuente</dt><dd>{data.source.access_conditions ?? unknown}</dd>
      <dt>Condiciones de redistribución de la fuente</dt><dd>{data.source.redistribution_conditions ?? unknown}</dd>
      <dt>Términos de uso</dt><dd><SafeLink url={data.source.terms_url} /></dd>
      <dt>Fecha de revisión de términos</dt><dd>{data.source.terms_checked_on ?? unknown}</dd>
    </dl>
    <h2>Localizadores</h2>
    <LocatorList locators={data.locators} />
    <h2>Procedencia</h2>
    <p>{data.provenance.total} observaciones</p>
    {full ? <FullProvenance datasetId={datasetId} /> : <>
      <Observations items={data.provenance.items} />
      {data.provenance.total > data.provenance.items.length &&
        <button onClick={() => setFull(true)}>Ver historial completo</button>}
    </>}
  </>}</StateView>;
}
