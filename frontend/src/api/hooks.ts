import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { request } from "./client";
import type {
  AuditDetail,
  AuditList,
  CreateAuditRequest,
  CreateAuditResponse,
  GeneratorInfo,
  Health,
  Preset,
  PriceResponse,
  TemplateInfo,
} from "./types";
export const useTemplates = () =>
  useQuery({
    queryKey: ["templates"],
    queryFn: () => request<TemplateInfo[]>("/strategies/templates"),
    staleTime: 300000,
  });
export const useGenerators = () =>
  useQuery({
    queryKey: ["generators"],
    queryFn: () => request<GeneratorInfo[]>("/generators"),
    staleTime: 300000,
  });
export const usePresets = () =>
  useQuery({
    queryKey: ["presets"],
    queryFn: () => request<Preset[]>("/presets"),
  });
export const useHealth = () =>
  useQuery({
    queryKey: ["health"],
    queryFn: () => request<Health>("/health"),
    refetchInterval: 30000,
    retry: 1,
  });
export const usePrices = (start: string, end: string) =>
  useQuery({
    queryKey: ["prices", "^NSEI", start, end],
    queryFn: () =>
      request<PriceResponse>(
        `/market/prices?symbol=%5ENSEI&start=${start}&end=${end}`,
      ),
    enabled: !!start && !!end && start < end,
    staleTime: 300000,
  });
export const useAudit = (id: string, poll = false) =>
  useQuery({
    queryKey: ["audit", id],
    queryFn: () => request<AuditDetail>(`/audits/${id}`),
    enabled: !!id,
    refetchInterval: poll ? 2000 : false,
  });
export const useAudits = (params = { limit: 50, offset: 0 }) =>
  useQuery({
    queryKey: ["audits", params],
    queryFn: () =>
      request<AuditList>(
        `/audits?${new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)]))}`,
      ),
  });
export function useCreateAudit() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (config: CreateAuditRequest) =>
      request<CreateAuditResponse>("/audits", {
        method: "POST",
        body: JSON.stringify(config),
      }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["audits"] }),
  });
}
export function useChart<T>(id: string, name: string, enabled = true) {
  return useQuery({
    queryKey: ["chart", id, name],
    queryFn: () => request<T>(`/audits/${id}/charts/${name}`),
    enabled: !!id && enabled,
    staleTime: Infinity,
  });
}
export function useRealism<T>(id: string) {
  return useQuery({
    queryKey: ["realism", id],
    queryFn: () => request<T>(`/generators/${id}/realism`),
    enabled: !!id,
    staleTime: 300000,
  });
}
