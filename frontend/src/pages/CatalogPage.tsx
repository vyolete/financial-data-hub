import { useState } from "react";
import { useQuery } from "../api/queries";
import { DatasetCard, Filters, Pagination, StateView, type SearchFilters } from "../components/catalog";

export function CatalogPage() {
  const [search, setSearch] = useState<SearchFilters & { page: number }>({
    q: "", provider: "", category: "", page: 1,
  });
  const datasets = useQuery("searchDatasets", search);
  const providers = useQuery("listProviders", { page_size: 100 });
  const categories = useQuery("listCategories", { page_size: 100 });

  return <>
    <h1>Catálogo de datasets</h1>
    <Filters
      providers={providers.state === "ready" ? providers.data.items : []}
      categories={categories.state === "ready" ? categories.data.items : []}
      onSearch={filters => setSearch({ ...filters, page: 1 })}
    />
    <StateView query={datasets} empty={data => data.total === 0}>{data => <>
      <div className="results">{data.items.map(dataset => <DatasetCard key={dataset.id} dataset={dataset} />)}</div>
      <Pagination value={data} onPage={page => setSearch(previous => ({ ...previous, page }))} />
    </>}</StateView>
  </>;
}
