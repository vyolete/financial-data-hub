import { useEffect, useState } from "react";
import { ApiError, get } from "./client";
import type { Operations } from "./schema";

const paths = {
  getHealth: "/health",
  searchDatasets: "/api/v1/datasets",
  getDataset: "/api/v1/datasets/{datasetId}",
  listDatasetProvenance: "/api/v1/datasets/{datasetId}/provenance",
  listProviders: "/api/v1/providers",
  listCategories: "/api/v1/categories",
  listRuns: "/api/v1/runs",
  getRun: "/api/v1/runs/{runId}",
} as const satisfies { [K in keyof Operations]: Operations[K]["path"] };

export type Query<T> =
  | { state: "loading" | "failed" | "missing" }
  | { state: "ready"; data: T };

export function useQuery<K extends keyof Operations>(
  operation: K, params: Operations[K]["params"],
): Query<Operations[K]["result"]> {
  const key = JSON.stringify(params);
  const [result, setResult] = useState<{
    operation: K; key: string; query: Query<Operations[K]["result"]>;
  }>();
  useEffect(() => {
    const controller = new AbortController();
    const parameters: Operations[K]["params"] = JSON.parse(key);
    void get<K>(paths[operation], parameters, controller.signal).then(
      data => {
        if (!controller.signal.aborted) setResult({ operation, key, query: { state: "ready", data } });
      },
      (error: unknown) => {
        if (!controller.signal.aborted) {
          const state = error instanceof ApiError && error.status === 404 ? "missing" : "failed";
          setResult({ operation, key, query: { state } });
        }
      },
    );
    return () => controller.abort();
  }, [operation, key]);
  return result?.operation === operation && result.key === key ? result.query : { state: "loading" };
}
